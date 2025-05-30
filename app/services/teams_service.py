from app.core.config import settings
from msal import ConfidentialClientApplication
from typing import Optional, Dict, Any, List

import logging
import httpx
import json
import time

logger = logging.getLogger("uvicorn.app")


class TeamsService:
    def __init__(self, tenant_id: Optional[str] = None, supabase=None) -> None:
        self.tenant_id = tenant_id or "common"
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
        )
        self.supabase = supabase
        self._transcript_cache = {}

    async def _fetch_with_retry(self, client, url, headers, max_retries=3):
        import asyncio
        import random

        for attempt in range(max_retries):
            try:
                response = await client.get(url, headers=headers)
                if response.status_code == 429:  # rate limited
                    retry_after = int(response.headers.get("retry-after", 60))
                    await asyncio.sleep(retry_after)
                    continue
                elif response.status_code >= 500:  # server errors
                    if attempt < max_retries - 1:
                        delay = (2**attempt) + random.uniform(
                            0, 1
                        )  # exponential backoff with jitter
                        await asyncio.sleep(delay)
                        continue
                return response
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    delay = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(delay)
                    continue
                raise
            except Exception:
                raise  # don't retry on other exceptions

        return response  # return last response if all retries exhausted

    def get_auth_url(
        self,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        state: Optional[str] = None,
    ) -> str:
        """Generate authorization URL for Microsoft OAuth"""
        logger.info("Generated callback URI: %s", redirect_uri)
        if scopes is None:
            scopes = [
                "User.Read",
                "OnlineMeetings.Read",
                "OnlineMeetingTranscript.Read.All",
                "Calendars.Read",
            ]
        return self.app.get_authorization_request_url(
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state or json.dumps({"tenant_id": self.tenant_id}),
            extra_scope_to_consent=["offline_access"],
        )

    async def get_token_from_code(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange auth code for access tokens"""
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=["https://graph.microsoft.com/.default"],
            redirect_uri=redirect_uri,
        )
        safe_result = {
            k: (v[:10] + "..." if k in ["access_token", "refresh_token"] else v)
            for k, v in result.items()
        }
        logger.info("Token response (safe): %s", safe_result)
        return result

    async def store_tokens(self, company_id: str, tokens: Dict[str, Any]) -> bool:
        """Store Microsoft tokens in Supabase database"""
        expires_in = tokens.get("expires_in", 3600)  # Default to 1 hr
        current_time = int(time.time())
        expires_on = current_time + expires_in

        token_data = {
            "company_id": company_id,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_on": expires_on,
            "scope": tokens.get("scope", ""),
        }

        if not token_data["access_token"] or not token_data["refresh_token"]:
            raise ValueError("Missing required token fields")

        logger.info("Storing token data for company_id: %s", company_id)
        logger.info("Token expires in %s seconds (at %s)", expires_in, expires_on)

        try:
            existing = (
                self.supabase.table("microsoft_tokens")
                .select("*")
                .eq("company_id", company_id)
                .execute()
            )

            existing = (
                self.supabase.table("microsoft_tokens")
                .select("*")
                .eq("company_id", company_id)
                .execute()
            )

            if existing.data and len(existing.data) > 0:
                # Update existing record
                _ = (
                    self.supabase.table("microsoft_tokens")
                    .update(token_data)
                    .eq("company_id", company_id)
                    .execute()
                )
            else:
                # Insert new record
                _ = self.supabase.table("microsoft_tokens").insert(token_data).execute()

            return True
        except Exception as e:
            logger.info("Database error storing tokens: %s", str(e), exc_info=True)
            raise ValueError(f"Failed to store tokens: {str(e)}")

    async def refresh_token(self, company_id: str) -> str:
        """Refresh Microsoft access token if expired"""
        # Get current tokens
        tokens_result = (
            self.supabase.table("microsoft_tokens")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        if not tokens_result.data:
            raise ValueError("No Microsoft tokens found for this company")

        token_data = tokens_result.data[0]
        current_time = int(time.time())
        expires_on = token_data.get("expires_on", 0)

        if expires_on > current_time + 300:
            logger.debug("Token still valid for company_id: %s", company_id)
            return token_data["access_token"]

        logger.info("Token expired for company_id: %s, refreshing", company_id)
        refresh_token = token_data["refresh_token"]

        if not refresh_token:
            raise ValueError("No refresh token available for this company")

        # Refresh the token
        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token, scopes=["https://graph.microsoft.com/.default"]
        )

        if "error" in result:
            raise ValueError(f"Token refresh failed: {result.get('error_description')}")

        # Update tokens in database
        await self.store_tokens(company_id, result)
        return result["access_token"]

    async def setup_notification_subscription(
        self, access_token, notification_url, expiration_minutes=43200
    ):
        """Set up webhook for notifications when new recordings are available"""
        # Maximum expiration time is 43200 minutes (30 days)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        from datetime import datetime, timedelta, timezone

        expiration_date = datetime.now(timezone.utc) + timedelta(
            minutes=expiration_minutes
        )
        expiration_iso = expiration_date.strftime("%Y-%m-%dT%H:%M:%SZ")

        subscription_data = {
            "changeType": "created,updated",
            "notificationUrl": notification_url,
            "resource": "/communications/onlineMeetings/recordings",
            "expirationDateTime": expiration_iso,
            "clientState": "callsightSecretState",  # Verify in webhook
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/subscriptions",
                headers=headers,
                json=subscription_data,
            )

            if response.status_code not in (200, 201):
                raise ValueError(f"Failed to set up subscription: {response.text}")

            return response.json()

    async def get_calendar_events(
        self,
        access_token: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """Get calendar events with meeting identifiers extracted"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        # Default to last 90 days if no dates provided
        if not start_date or not end_date:
            from datetime import datetime, timedelta, timezone

            end_dt = datetime.now(timezone.utc)
            start_dt = end_dt - timedelta(days=90)
            start_date = start_dt.strftime("%Y-%m-%dT00:00:00Z")
            end_date = end_dt.strftime("%Y-%m-%dT23:59:59Z")

        result = []
        async with httpx.AsyncClient() as client:
            try:
                # Use calendarView for date filtering
                calendar_url = f"https://graph.microsoft.com/v1.0/me/calendarView?startDateTime={start_date}&endDateTime={end_date}"
                response = await client.get(calendar_url, headers=headers)
                response.raise_for_status()
                events = response.json().get("value", [])

                logger.info("Found %s calendar events", len(events))

                # Extract meeting info from each event
                for event in events:
                    meeting_info = {
                        "event_id": event.get("id"),
                        "subject": event.get("subject"),
                        "start": event.get("start"),
                        "end": event.get("end"),
                        "organizer": event.get("organizer", {})
                        .get("emailAddress", {})
                        .get("address"),
                        "attendees_count": len(event.get("attendees", [])),
                        "has_online_meeting": bool(event.get("onlineMeeting")),
                        "meeting_identifiers": [],
                    }

                    # Extract Teams meeting identifiers
                    online_meeting = event.get("onlineMeeting")
                    if online_meeting:
                        join_url = online_meeting.get("joinUrl")
                        if join_url:
                            meeting_info["meeting_identifiers"].append(
                                {
                                    "type": "joinUrl",
                                    "value": join_url,
                                    "extracted_id": self._extract_meeting_id_from_url(
                                        join_url
                                    ),
                                }
                            )

                    # Also check body and location for Teams URLs
                    body_content = event.get("body", {}).get("content", "")
                    location = event.get("location", {}).get("displayName", "")

                    # Look for Teams URLs in body/location
                    teams_urls = self._find_teams_urls(body_content + " " + location)
                    for url in teams_urls:
                        meeting_info["meeting_identifiers"].append(
                            {
                                "type": "body_url",
                                "value": url,
                                "extracted_id": self._extract_meeting_id_from_url(url),
                            }
                        )

                    # Only include events that have some kind of meeting identifier
                    if (
                        meeting_info["meeting_identifiers"]
                        or meeting_info["has_online_meeting"]
                    ):
                        result.append(meeting_info)

                logger.info("Found %s events with meeting identifiers", len(result))
                return result

            except httpx.HTTPStatusError as e:
                return {
                    "error": f"http error: {e.response.status_code}, {e.response.text}"
                }
            except Exception as e:
                return {"error": f"failed to fetch calendar events: {str(e)}"}

    async def get_online_meetings_from_events(self, access_token, join_url):
        """Get list of meetings that have recordings"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        filter_param = f"JoinWebUrl%20eq%20'{join_url}'"

        # Fetch meetings
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/onlineMeetings?$filter={filter_param}",
                headers=headers,
            )

            if response.status_code != 200:
                raise ValueError(f"Failed to get meetings: {response.text}")

            meetings = response.json().get("value", [])

        return meetings

    async def get_transcripts_from_meetings(self, access_token, meetings):
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        content_headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "text/vtt",
        }

        meeting_ids = [meeting["id"] for meeting in meetings]
        logger.info("Processing %s meetings for transcripts", len(meeting_ids))

        transcript_contents = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                for i, meeting_id in enumerate(meeting_ids):
                    logger.info(
                        "Processing meeting %s/%s: %s",
                        i + 1,
                        len(meeting_ids),
                        meeting_id,
                    )
                    try:
                        # Get transcript metadata
                        response = await self._fetch_with_retry(
                            client,
                            f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts",
                            headers,
                        )

                        if response.status_code != 200:
                            logger.info(
                                "Failed to get transcripts for meeting %s: HTTP %s - %s",
                                meeting_id,
                                response.status_code,
                                response.text[:200],
                            )
                            continue

                        transcripts = response.json().get("value", [])
                        logger.info(
                            "Found %s transcripts for meeting %s",
                            len(transcripts),
                            meeting_id,
                        )

                        # For each transcript, get the content
                        for j, transcript in enumerate(transcripts):
                            content_url = transcript.get("transcriptContentUrl")
                            transcript_id = transcript.get("id")

                            if not content_url:
                                logger.info(
                                    "No content URL for transcript %s", transcript_id
                                )
                                transcript["content"] = "No content URL available"
                                transcript_contents.append(transcript)
                                continue

                            try:
                                logger.info(
                                    "Fetching content for transcript %s (meeting %s)",
                                    transcript_id,
                                    meeting_id,
                                )
                                cache_key = f"{meeting_id}_{transcript_id}"
                                if cache_key in self._transcript_cache:
                                    logger.info(
                                        "Using cached content for transcript %s",
                                        transcript_id,
                                    )
                                    transcript["content"] = self._transcript_cache[
                                        cache_key
                                    ]["content"]
                                    transcript["content_type"] = self._transcript_cache[
                                        cache_key
                                    ]["content_type"]
                                    transcript_contents.append(transcript)
                                    continue

                                content_response = await self._fetch_with_retry(
                                    client, content_url, content_headers
                                )

                                if content_response.status_code == 200:
                                    transcript["content"] = (
                                        self._extract_text_with_speakers(
                                            content_response.text
                                        )
                                    )
                                    transcript["content_type"] = (
                                        content_response.headers.get("content-type", "")
                                    )
                                    logger.info(
                                        "Successfully extracted content for transcript %s",
                                        transcript_id,
                                    )
                                    self._transcript_cache[cache_key] = {
                                        "content": transcript["content"],
                                        "content_type": transcript["content_type"],
                                    }
                                else:
                                    error_msg = f"Failed to fetch content: HTTP {content_response.status_code} - {content_response.text[:200]}"
                                    transcript["content"] = error_msg
                                    logger.info(
                                        "Failed to get content for transcript %s: %s",
                                        transcript_id,
                                        error_msg,
                                    )

                            except httpx.TimeoutException as e:
                                error_msg = f"Timeout fetching content: {str(e)}"
                                transcript["content"] = error_msg
                                logger.info(
                                    "Timeout getting content for transcript %s: %s",
                                    transcript_id,
                                    str(e),
                                )
                            except Exception as e:
                                error_msg = f"Exception fetching content: {str(e)}"
                                transcript["content"] = error_msg
                                logger.info(
                                    "Exception getting content for transcript %s: %s",
                                    transcript_id,
                                    str(e),
                                    exc_info=True,
                                )

                            transcript_contents.append(transcript)

                    except httpx.TimeoutException as e:
                        logger.info(
                            "Timeout getting transcripts for meeting %s: %s",
                            meeting_id,
                            str(e),
                        )
                        continue
                    except Exception as e:
                        logger.info(
                            "Exception processing meeting %s: %s",
                            meeting_id,
                            str(e),
                            exc_info=True,
                        )
                        continue

            except Exception as e:
                error_msg = f"Major error in get_transcripts_from_meetings: {str(e)}"
                logger.info(error_msg, exc_info=True)
                return {"error": error_msg}

        return transcript_contents

    def _get_transcript_text(self, transcripts):
        all_text_segments = []

        for transcript in transcripts:
            content = transcript.get("content", "")
            if not content:
                continue

            # Split by lines and extract just the spoken text
            lines = content.strip().split("\n")
            for line in lines:
                if ":" in line:
                    # Split on first colon to separate speaker from text
                    _, text = line.split(":", 1)
                    text = text.strip()
                    if text:  # Only add non-empty text
                        all_text_segments.append(text)

        # Join all text segments with spaces
        combined_text = " ".join(all_text_segments)

        return combined_text.strip()

    def _extract_meeting_id_from_url(self, url):
        """Extract meeting ID from Teams URL - basic implementation"""
        import re
        from urllib.parse import unquote

        decoded_url = unquote(url)

        # Teams URLs often contain thread IDs or meeting IDs
        patterns = [
            # threadId parameter (from meetingOptions URLs)
            r"threadId=([^&]+)",
            # meeting thread from meetup-join URLs
            r"19%3ameeting_([^%]+)%40thread\.v2",
            # decoded version
            r"19_meeting_([^@]+)@thread\.v2",
            r"19_meeting_([^@]+)@thread\.v2",
            # fallback patterns
            r"meetingID=([^&]+)",
            r"conversations/([^/]+)",
            r"meetingID=([^&]+)",
            r"conversations/([^/]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, decoded_url)
            if match:
                extracted = match.group(1)
                # For meeting patterns, reconstruct full thread ID
                if "meeting_" in pattern:
                    if not extracted.startswith("19_meeting_"):
                        extracted = f"19_meeting_{extracted}@thread.v2"
                return extracted

        return None

    def _find_teams_urls(self, text):
        """Find Teams meeting URLs in text"""
        import re

        # Look for Teams URLs
        teams_pattern = r'https://teams\.microsoft\.com/[^\s<>"\[\]{}|\\^`]+'
        return re.findall(teams_pattern, text, re.IGNORECASE)

    def _extract_text_with_speakers(self, vtt_content):
        import re

        content = re.sub(r"^WEBVTT\r?\n\r?\n", "", vtt_content)

        # Extract speaker and text
        speaker_matches = re.findall(r"<v ([^>]+)>([^<]+)</v>", content)

        # Format as "Speaker: text"
        formatted_text = []
        for speaker, text in speaker_matches:
            formatted_text.append(f"{speaker}: {text.strip()}")

        return "\n".join(formatted_text)
