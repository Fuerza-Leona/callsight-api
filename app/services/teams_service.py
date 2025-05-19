from app.core.config import settings
from msal import ConfidentialClientApplication
import httpx

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
    
    def get_auth_url(self, redirect_uri, scopes=None):
        """Generate authorization URL for Microsoft OAuth"""
        if scopes is None:
            scopes = [
                "https://graph.microsoft.com/OnlineMeetings.Read.All",
                "https://graph.microsoft.com/OnlineMeetingRecording.Read.All",
                "https://graph.microsoft.com/OnlineMeetingTranscript.Read.All",
                "offline_access"  # This gives you refresh tokens
            ]
        return self.app.get_authorization_request_url(
            scopes=scopes,
            redirect_uri=redirect_uri,
            state={"tenant_id": self.tenant_id}
        )
    
    async def get_token_from_code(self, code, redirect_uri):
        """Exchange auth code for access tokens"""
        result = self.app.acquire_token_by_authorization_code(
            code=code,
            scopes=["https://graph.microsoft.com/.default"],
            redirect_uri=redirect_uri
        )
        return result
    
    async def store_tokens(self, supabase, company_id, tokens):
        """Store Microsoft tokens in Supabase database"""
        # First check if tokens already exist
        existing = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
        
        token_data = {
            "company_id": company_id,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "expires_on": tokens["expires_on"],
            "scope": tokens.get("scope", "")
        }
        
        if existing.data and len(existing.data) > 0:
            # Update existing record
            supabase.table("microsoft_tokens").update(token_data).eq("company_id", company_id).execute()
        else:
            # Insert new record
            supabase.table("microsoft_tokens").insert(token_data).execute()
            
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
        
        # First get all online meetings
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/onlineMeetings",
                headers=headers
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
    
    async def setup_notification_subscription(self, access_token, notification_url, expiration_minutes=43200):
        """Set up webhook for notifications when new recordings are available"""
        # Maximum expiration time is 43200 minutes (30 days)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        subscription_data = {
            "changeType": "created,updated",
            "notificationUrl": notification_url,
            "resource": "/communications/onlineMeetings/recordings",
            "expirationDateTime": f"P{expiration_minutes}M",
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
