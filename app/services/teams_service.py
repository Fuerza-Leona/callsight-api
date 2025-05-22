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
                "OnlineMeetingTranscript.Read.All"
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
    
    async def get_meetings_with_recordings(self, access_token, start_date=None, end_date=None):
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
        filter_param = f"startDateTime ge {start_date} and endDateTime le {end_date}"
        
        # Fetch meetings
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/onlineMeetings/",
                headers=headers,
            )
            
            if response.status_code != 200:
                raise ValueError(f"Failed to get meetings: {response.text}")
                
            meetings = response.json().get("value", [])
            
            # Filter for meetings with recordings
            result = []
            for meeting in meetings:
                meeting_id = meeting["id"]
                # Check if this meeting has a recording
                recording_response = await client.get(
                    f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{meeting_id}/recordings",
                    headers=headers
                )
                
                if recording_response.status_code == 200 and recording_response.json().get("value", []):
                    meeting["recordings"] = recording_response.json().get("value", [])
                    result.append(meeting)
            
            return result
    
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
            "authorization": f"bearer {access_token}",
            "content-type": "application/json"
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
