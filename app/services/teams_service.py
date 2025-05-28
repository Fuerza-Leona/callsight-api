from app.core.config import settings
from msal import ConfidentialClientApplication
import httpx
import json
import time

class TeamsService:
    def __init__(self, tenant_id=None):
        self.tenant_id = tenant_id or "common"
        self.client_id = settings.MICROSOFT_CLIENT_ID
        self.client_secret = settings.MICROSOFT_CLIENT_SECRET
        self.app = ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}"
        )
    
    def get_auth_url(self, redirect_uri, scopes=None, state=None):
        """Generate authorization URL for Microsoft OAuth"""
        print(f"Generated callback URI: {redirect_uri}")
        if scopes is None:
            scopes = [
                "User.Read",
                "OnlineMeetings.Read",
                "OnlineMeetingTranscript.Read.All",
                "Calendars.Read"
            ]
        return self.app.get_authorization_request_url(
            scopes=scopes,
            redirect_uri=redirect_uri,
            state=state or json.dumps({"tenant_id": self.tenant_id}),
            extra_scope_to_consent=["offline_access"]
        )
    
    async def get_token_from_code(self, code, redirect_uri):
        """Exchange auth code for access tokens"""
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=["https://graph.microsoft.com/.default"],
            redirect_uri=redirect_uri
        )
        safe_result = {k: (v[:10] + "..." if k in ["access_token", "refresh_token"] else v) 
                   for k, v in result.items()}
        print(f"Token response (safe): {safe_result}")
        return result
    
    async def store_tokens(self, supabase, company_id, tokens):
        """Store Microsoft tokens in Supabase database"""
        expires_in = tokens.get('expires_in', 3600)  # Default to 1 hr
        current_time = int(time.time())
        expires_on = current_time + expires_in
        
        token_data = {
            "company_id": company_id,
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "expires_on": expires_on,
            "scope": tokens.get("scope", "")
        }
        
        if not token_data["access_token"] or not token_data["refresh_token"]:
            raise ValueError("Missing required token fields")
    
        print(f"Storing token data for company_id: {company_id}")
        print(f"Token expires in {expires_in} seconds (at {expires_on})")
        
        try:
            existing = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
            
            if existing.data and len(existing.data) > 0:
                # Update existing record
                result = supabase.table("microsoft_tokens").update(token_data).eq("company_id", company_id).execute()
            else:
                # Insert new record
                result = supabase.table("microsoft_tokens").insert(token_data).execute()
            
            return True
        except Exception as e:
            print(f"Database error storing tokens: {str(e)}")
            raise ValueError(f"Failed to store tokens: {str(e)}")
            
    async def refresh_token(self, supabase, company_id):
        """Refresh Microsoft access token if expired"""
        # Get current tokens
        tokens_result = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
        if not tokens_result.data:
            raise ValueError("No Microsoft tokens found for this company")
            
        token_data = tokens_result.data[0]
        refresh_token = token_data["refresh_token"]
        
        # Refresh the token
        result = self.app.acquire_token_by_refresh_token(
            refresh_token=refresh_token,
            scopes=["https://graph.microsoft.com/.default"]
        )
        
        if "error" in result:
            raise ValueError(f"Token refresh failed: {result.get('error_description')}")
            
        # Update tokens in database
        await self.store_tokens(supabase, company_id, result)
        return result["access_token"]
    
    async def get_meetings(self, access_token, start_date=None, end_date=None):
        """Get list of meetings that have recordings"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        if not start_date:
            from datetime import datetime, timedelta, timezone
            start_date = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%Y-%m-%dT00:00:00Z")
        if not end_date:
            from datetime import datetime, timedelta
            end_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
            
        # Filtering
        filter_param = f"JoinWebUrl%20eq%20'https://teams.microsoft.com/l/meetup-join/19%3ameeting_Y2FkNjIzN2MtNjljMC00NjQwLTgwNzMtZTk2NGU2ZDEyYmUy%40thread.v2/0?context=%7b%22Tid%22%3a%2225edc74d-6ecf-4a26-ad86-fb3019a81dae%22%2c%22Oid%22%3a%2221054d65-46c5-4f72-a2f6-91962987f348%22%7d'"
        
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
    
    async def get_recording_download_url(self, access_token, meeting_id, recording_id):
        """Get download URL for a specific recording"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/recordings/{recording_id}",
                headers=headers
            )
            
            if response.status_code != 200:
                raise ValueError(f"Failed to get recording: {response.text}")
                
            return response.json().get("downloadUrl")
        
    async def get_meeting_transcripts(self, access_token, meeting_id):
        """Get transcripts for a specific meeting"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts",
                headers=headers
            )
            
            if response.status_code != 200:
                raise ValueError(f"Failed to get transcripts: {response.text}")
                
            transcripts = response.json().get("value", [])
            
            # For each transcript, get the actual content
            for transcript in transcripts:
                transcript_id = transcript["id"]
                content_response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
                    headers=headers
                )
                
                if content_response.status_code == 200:
                    transcript["content"] = content_response.json()
            
            return transcripts
        
    async def get_transcripts(self, access_token):
        """get all transcripts by iterating over user’s online meetings"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        result = []
        async with httpx.AsyncClient() as client:
            try:
                # Get all online meetings
                meetings_url = "https://graph.microsoft.com/v1.0/me/onlineMeetings"
                meetings_response = await client.get(meetings_url, headers=headers)
                meetings_response.raise_for_status()
                meetings = meetings_response.json().get("value", [])
                
                print("meetings length: ", len(meetings))
                
                # Iterate through meetings to get transcripts
                for meeting in meetings:
                    meeting_id = meeting.get("id")
                    transcripts_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
                    transcripts_response = await client.get(transcripts_url, headers=headers)
                    
                    if transcripts_response.status_code == 200:
                        transcripts = transcripts_response.json().get("value", [])
                        for transcript in transcripts:
                            content_url = transcript.get("transcriptContentUrl")
                            if content_url:
                                content_response = await client.get(content_url + "?$format=text/vtt", headers=headers)
                                transcript["content"] = content_response.text if content_response.status_code == 200 else None
                            result.append(transcript)
            except httpx.HTTPStatusError as e:
                return {"error": f"http error: {e.response.status_code}, {e.response.text}"}
            except Exception as e:
                return {"error": f"failed to fetch transcripts: {str(e)}"}
        
        return result
    
    async def get_calendar_events(self, access_token, start_date=None, end_date=None):
        """Get calendar events with meeting identifiers extracted"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
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
                
                print(f"Found {len(events)} calendar events")
                
                # Extract meeting info from each event
                for event in events:
                    meeting_info = {
                        "event_id": event.get("id"),
                        "subject": event.get("subject"),
                        "start": event.get("start"),
                        "end": event.get("end"),
                        "organizer": event.get("organizer", {}).get("emailAddress", {}).get("address"),
                        "attendees_count": len(event.get("attendees", [])),
                        "has_online_meeting": bool(event.get("onlineMeeting")),
                        "meeting_identifiers": []
                    }
                    
                    # Extract Teams meeting identifiers
                    online_meeting = event.get("onlineMeeting")
                    if online_meeting:
                        join_url = online_meeting.get("joinUrl")
                        if join_url:
                            meeting_info["meeting_identifiers"].append({
                                "type": "joinUrl",
                                "value": join_url,
                                "extracted_id": self._extract_meeting_id_from_url(join_url)
                            })
                    
                    # Also check body and location for Teams URLs
                    body_content = event.get("body", {}).get("content", "")
                    location = event.get("location", {}).get("displayName", "")
                    
                    # Look for Teams URLs in body/location
                    teams_urls = self._find_teams_urls(body_content + " " + location)
                    for url in teams_urls:
                        meeting_info["meeting_identifiers"].append({
                            "type": "body_url",
                            "value": url,
                            "extracted_id": self._extract_meeting_id_from_url(url)
                        })
                    
                    # Only include events that have some kind of meeting identifier
                    if meeting_info["meeting_identifiers"] or meeting_info["has_online_meeting"]:
                        result.append(meeting_info)
                
                print(f"Found {len(result)} events with meeting identifiers")
                return result
                
            except httpx.HTTPStatusError as e:
                return {"error": f"http error: {e.response.status_code}, {e.response.text}"}
            except Exception as e:
                return {"error": f"failed to fetch calendar events: {str(e)}"}
            
    async def get_online_meetings_from_events(self, access_token, join_url):
        """Get list of meetings that have recordings"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
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
            "Content-Type": "application/json"
        }
         
         content_headers = {
             "Authorization": f"Bearer {access_token}",
             "Accept": "text/vtt" 
         }
         
         meeting_ids = [meeting["id"] for meeting in meetings]
         
         transcripts = []
         transcript_contents = []
         
            # Fetch meetings
         async with httpx.AsyncClient() as client:
             try:
                 for meeting_id in meeting_ids:
                    # Get transcript metadata
                    response = await client.get(
                        f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts",
                        headers=headers,
                    )
                    
                    if response.status_code != 200:
                        print(f"Failed to get transcripts for meeting {meeting_id}: {response.status_code}")
                        continue
                        
                    transcripts = response.json().get("value", [])
                    
                    # For each transcript, get the content
                    for transcript in transcripts:
                        content_url = transcript.get("transcriptContentUrl")
                        if content_url:
                            content_response = await client.get(content_url, headers=content_headers)
                        
                        if content_response.status_code == 200:
                            # Content is usually text, not json
                            transcript["content"] = self._extract_text_with_speakers(content_response.text)
                            transcript["content_type"] = content_response.headers.get("content-type", "")
                        else:
                            transcript["content"] = f"Failed to fetch: {content_response.status_code}, {content_response.text}"
                            # print(f"Failed to get content for transcript {transcript_id}: {content_response.status_code}")
                            # print(f"Error details: {content_response.text}")
                    
                        transcript_contents.append(transcript)
                    
             except Exception as e:
                return {"error": f"failed to fetch transcripts: {str(e)}"}
            
         return transcript_contents
     
    def _get_transcript_text(self, transcripts):
        all_text_segments = []
   
        for transcript in transcripts:
            content = transcript.get("content", "")
            if not content:
                continue
                
            # Split by lines and extract just the spoken text
            lines = content.strip().split('\n')
            for line in lines:
                if ':' in line:
                    # Split on first colon to separate speaker from text
                    _, text = line.split(':', 1)
                    text = text.strip()
                    if text:  # Only add non-empty text
                        all_text_segments.append(text)
        
        # Join all text segments with spaces
        combined_text = ' '.join(all_text_segments)
        
        return combined_text.strip()
        
    def _extract_meeting_id_from_url(self, url):
        """Extract meeting ID from Teams URL - basic implementation"""
        import re
        from urllib.parse import unquote
        
        decoded_url = unquote(url)
        
        # Teams URLs often contain thread IDs or meeting IDs
        patterns = [
            # threadId parameter (from meetingOptions URLs)
            r'threadId=([^&]+)',
            # meeting thread from meetup-join URLs  
            r'19%3ameeting_([^%]+)%40thread\.v2',
            # decoded version
            r'19_meeting_([^@]+)@thread\.v2',
            # fallback patterns
            r'meetingID=([^&]+)',
            r'conversations/([^/]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, decoded_url)
            if match:
                extracted = match.group(1)
                # For meeting patterns, reconstruct full thread ID
                if 'meeting_' in pattern:
                    if not extracted.startswith('19_meeting_'):
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
        content = re.sub(r'^WEBVTT\r?\n\r?\n', '', vtt_content)
        
        # Extract speaker and text
        speaker_matches = re.findall(r'<v ([^>]+)>([^<]+)</v>', content)
        
        # Format as "Speaker: text"
        formatted_text = []
        for speaker, text in speaker_matches:
            formatted_text.append(f"{speaker}: {text.strip()}")
        
        return '\n'.join(formatted_text)
    
    async def resolve_meeting_id_from_join_url(self, access_token, join_url):
        """Get the actual meeting ID from a join URL using graph api filter"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        # URL encode the join URL for the filter
        from urllib.parse import quote
        encoded_join_url = quote(join_url, safe='')
        
        async with httpx.AsyncClient() as client:
            try:
                # Use the filter endpoint to find meeting by join URL
                filter_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings?$filter=JoinWebUrl eq '{join_url}'"
                response = await client.get(filter_url, headers=headers)
                
                if response.status_code == 200:
                    meetings = response.json().get("value", [])
                    if meetings:
                        meeting = meetings[0]  # Should only be one match
                        return {
                            "success": True,
                            "meeting_id": meeting.get("id"),
                            "thread_id": meeting.get("chatInfo", {}).get("threadId"),
                            "subject": meeting.get("subject"),
                            "meeting_object": meeting
                        }
                    else:
                        return {"success": False, "error": "No meeting found for this join URL"}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                    
            except Exception as e:
                return {"success": False, "error": f"Request failed: {str(e)}"}

    async def get_transcripts_for_meeting_id(self, access_token, meeting_id):
        """Get transcripts for a specific meeting ID"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            try:
                # Try the transcript endpoint
                transcript_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts"
                response = await client.get(transcript_url, headers=headers)
                
                if response.status_code == 200:
                    transcripts = response.json().get("value", [])
                    
                    # Get content for each transcript
                    for transcript in transcripts:
                        transcript_id = transcript.get("id")
                        content_url = f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content"
                        
                        content_response = await client.get(content_url, headers=headers)
                        if content_response.status_code == 200:
                            # Content might be in different formats
                            content_type = content_response.headers.get('content-type', '')
                            if 'json' in content_type:
                                transcript["content"] = content_response.json()
                            else:
                                transcript["content"] = content_response.text
                        else:
                            transcript["content"] = f"Failed to get content: {content_response.status_code}"
                    
                    return {"success": True, "transcripts": transcripts}
                else:
                    return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                    
            except Exception as e:
                return {"success": False, "error": f"Request failed: {str(e)}"}
    
    async def get_all_transcripts_from_calendar(self, access_token, start_date=None, end_date=None):
        """The complete solution: calendar events -> meeting IDs -> transcripts"""
        # Step 1: Get calendar events
        events = await self.get_calendar_events(access_token, start_date, end_date)
        if not isinstance(events, list):
            return events
        
        all_transcripts = []
        
        # Step 2: For each event, resolve meeting ID and get transcripts
        for event in events:
            event_result = {
                "event_id": event.get("event_id"),
                "subject": event.get("subject"),
                "start": event.get("start"),
                "organizer": event.get("organizer"),
                "transcripts": [],
                "resolution_errors": []
            }
            
            # Try each join URL in the event
            for identifier in event.get("meeting_identifiers", []):
                if identifier.get("type") in ["joinUrl", "body_url"]:
                    join_url = identifier.get("value")
                    
                    # Resolve to actual meeting ID
                    resolution = await self.resolve_meeting_id_from_join_url(access_token, join_url)
                    
                    if resolution.get("success"):
                        meeting_id = resolution.get("meeting_id")
                        
                        # Get transcripts for this meeting
                        transcript_result = await self.get_transcripts_for_meeting_id(access_token, meeting_id)
                        
                        if transcript_result.get("success"):
                            event_result["transcripts"].extend(transcript_result.get("transcripts", []))
                        else:
                            event_result["resolution_errors"].append({
                                "step": "transcript_fetch",
                                "meeting_id": meeting_id,
                                "error": transcript_result.get("error")
                            })
                    else:
                        event_result["resolution_errors"].append({
                            "step": "meeting_resolution",
                            "join_url": join_url,
                            "error": resolution.get("error")
                        })
            
            # Only include events that have some data
            if event_result["transcripts"] or event_result["resolution_errors"]:
                all_transcripts.append(event_result)
        
        return all_transcripts
        
    async def setup_notification_subscription(self, access_token, notification_url, expiration_minutes=43200):
        """Set up webhook for notifications when new recordings are available"""
        # Maximum expiration time is 43200 minutes (30 days)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        from datetime import datetime, timedelta
        expiration_date = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        expiration_iso = expiration_date.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        subscription_data = {
            "changeType": "created,updated",
            "notificationUrl": notification_url,
            "resource": "/communications/onlineMeetings/recordings",
            "expirationDateTime": expiration_iso,
            "clientState": "callsightSecretState"  # Verify in webhook
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/subscriptions",
                headers=headers,
                json=subscription_data
            )
            
            if response.status_code not in (200, 201):
                raise ValueError(f"Failed to set up subscription: {response.text}")
                
            return response.json()
