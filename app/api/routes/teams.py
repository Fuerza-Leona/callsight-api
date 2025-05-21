from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from app.services.teams_service import TeamsService
from app.core.config import settings
from app.api.deps import get_current_user
from app.db.session import get_supabase
import json
import httpx

router = APIRouter(prefix="/teams", tags=["teams"])

@router.get("/connect")
async def connect_teams(
    request: Request, 
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """Start Microsoft Teams integration OAuth flow"""
    # Get user's company ID
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    company_id = user_response.data[0]["company_id"]
    
    # Get company information to determine tenant ID
    company_response = supabase.table("company_client").select("*").eq("company_id", company_id).execute()
    if not company_response.data:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Initialize Teams service
    teams_service = TeamsService()
    
    # Generate callback URL
    base_url = str(request.base_url)
    if base_url.endswith('/'):
        base_url = base_url[:-1]
    callback_url = f"{base_url}{settings.API_V1_STR}/teams/callback"
    
    # Generate auth URL
    state = json.dumps({"company_id": company_id, "tenant_id": "common"})
    
    auth_url = teams_service.get_auth_url(callback_url, state=state)
    
    # Save company_id in session or cookie
    response = Response()
    response.set_cookie(key="connecting_company_id", value=company_id, httponly=True)
    print(f"Set company id to: {company_id}")
    
    return {"auth_url": auth_url}

@router.get("/callback")
async def teams_callback(
    request: Request,
    code: str,
    state: str = None,
    error: str = None,
    error_description: str = None,
    supabase = Depends(get_supabase)
):
    """Handle Microsoft OAuth callback"""
    print(f"Callback received! code: {code[:10]}... error: {error} state: {state}")
    
    try:
        state_data = json.loads(state) if state else {}
        company_id = state_data.get("company_id")
        tenant_id = state_data.get("tenant_id")
        
        if not company_id:
            raise HTTPException(
                status_code=400, 
                detail="Missing company context. Restart authorization."
            )
        
        teams_service = TeamsService(tenant_id=tenant_id)
        
            # Exchange code for tokens
        base_url = str(request.base_url)
        if base_url.endswith('/'):
            base_url = base_url[:-1]
        callback_url = f"{base_url}{settings.API_V1_STR}/teams/callback"
        
        token_result = await teams_service.get_token_from_code(code, callback_url)
        
        if "error" in token_result:
            raise HTTPException(
                status_code=400, 
                detail=f"Token error: {token_result.get('error_description')}"
            )
            
        # Store tokens in database
        await teams_service.store_tokens(supabase, company_id, token_result)
        
        # Set up webhook for notifications
        if base_url.startswith("http://"):
            print("Skipping webhook setup in non-secure environment...")
        else:
            notification_url = f"{base_url}{settings.API_V1_STR}/teams/notifications"
            try:
                await teams_service.setup_notification_subscription(
                    token_result["access_token"],
                    notification_url
                )
            except Exception as e:
                print(f"Warning: Failed to set up notification subscription: {str(e)}")
        
        # Success and redirect
        devenv = settings.NODE_ENV
        
        redirect_url = f"{base_url}/perfil" if devenv != "development" else "http://localhost:3000/perfil"
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Integration error: {str(e)}")

@router.get("/recordings")
async def list_recordings(
    start_date: str = None,     # Format: YYYY-MM-DD
    end_date: str = None,       # Format: YYYY-MM-DD
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """List available recordings from Teams"""
    # Get user's company ID
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    company_id = user_response.data[0]["company_id"]
    
    # Get Microsoft tokens from database
    tokens_response = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
    if not tokens_response.data:
        raise HTTPException(status_code=404, detail="Microsoft Teams integration not set up for this company")
    
    # Initialize Teams service
    teams_service = TeamsService()
    
    try:
        # Refresh token if needed
        access_token = await teams_service.refresh_token(supabase, company_id)
        
        # Fetch recordings
        recordings = await teams_service.get_meetings_with_recordings(access_token, start_date, end_date)
        
        return {"recordings": recordings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recordings: {str(e)}")
    
router.get("/all-recordings")
async def get_all_recordings(
    chunks: int = 10,
    chunk_size: int = 90,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """Fetch all available recordings by chunking requests over time"""
    from datetime import datetime, timedelta, timezone
    
    # Get tokens
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    company_id = user_response.data[0]["company_id"]
    tokens_response = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
    if not tokens_response.data:
        raise HTTPException(status_code=404, detail="Microsoft Teams integration not set up for this company")
    
    teams_service = TeamsService()
    access_token = await teams_service.refresh_token(supabase, company_id)
    
    # Calculate date chunks working backward from today
    end_date = datetime.now(timezone.utc)
    all_recordings = []
    
    for i in range(chunks):
        chunk_end = end_date - timedelta(days=i * chunk_size)
        chunk_start = chunk_end - timedelta(days=chunk_size)
        
        start_str = chunk_start.strftime("%Y-%m-%d")
        end_str = chunk_end.strftime("%Y-%m-%d")
        
        try:
            print(f"Fetching chunk {i+1}/{chunks}: {start_str} to {end_str}")
            recordings = await teams_service.get_meetings_with_recordings(
                access_token, start_str, end_str
            )
            all_recordings.extend(recordings)
        except Exception as e:
            print(f"Error fetching chunk {i+1}: {str(e)}")
            # Continue with next
    
    return {"recordings": all_recordings, "total": len(all_recordings)}
    
@router.get("/transcripts")
async def list_transcripts(
    meeting_id: str,
    current_user=Depends(get_current_user),
    supabase=Depends(get_supabase)
):
    """List available transcripts from Teams"""
    # Get user's company ID
    user_response = supabase.table("users").select("company_id").eq("user_id", current_user.id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    company_id = user_response.data[0]["company_id"]
    
    # Get Microsoft tokens from database
    tokens_response = supabase.table("microsoft_tokens").select("*").eq("company_id", company_id).execute()
    if not tokens_response.data:
        raise HTTPException(status_code=404, detail="Microsoft Teams integration not set up for this company")
    
    # Initialize Teams service
    teams_service = TeamsService()
    
    try:
        # Refresh token if needed
        access_token = await teams_service.refresh_token(supabase, company_id)
        
        # Fetch recordings
        transcripts = await teams_service.get_meeting_transcripts(access_token, meeting_id)
        
        return {"transcripts": transcripts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch recordings: {str(e)}")

@router.post("/notifications")
async def handle_notifications(
    request: Request,
    supabase=Depends(get_supabase)
):
    """Webhook endpoint to receive notifications about new recordings"""
    try:
        # Get the notification payload
        notification = await request.json()
        
        # Verify the notification
        validation_token = request.query_params.get("validationToken")
        if validation_token:
            # This is a subscription validation request
            return Response(content=validation_token, media_type="text/plain")
        
        # Check clientState for security
        client_state = notification.get("clientState")
        if client_state != "callsightSecretState":
            return Response(status_code=401)
        
        # Process the notification
        value = notification.get("value", [])
        for change_notification in value:
            resource_data = change_notification.get("resourceData", {})
            
            # Example: When a new recording is available
            # Process each notification and kick off your existing
            # audio processing pipeline
            
            # For demonstration purposes, just log it
            print(f"Received notification: {json.dumps(change_notification)}")
        
        # Acknowledge receipt of the notification
        return Response(status_code=202)
    except Exception as e:
        print(f"Error processing notification: {str(e)}")
        return Response(status_code=500)
    
@router.get("/test-config")
async def test_config():
    teams_service = TeamsService()
    test_url = teams_service.get_auth_url("https://example.com/callback")
    parsed_url = httpx.URL(test_url)
    query_params = dict(parsed_url.params)
    
    safe_params = {k: (v[:10] + "..." if k == "client_id" else v) for k, v in query_params.items()}
    
    return {
        "auth_url_generated": True,
        "url_params": safe_params,
        "microsoft_config_valid": bool(settings.MICROSOFT_CLIENT_ID and settings.MICROSOFT_CLIENT_SECRET)
    }