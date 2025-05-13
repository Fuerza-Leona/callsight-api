from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from supabase import Client
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from enum import Enum
from app.core.config import settings

from app.db.session import get_supabase
from app.api.deps import get_current_user


router = APIRouter(prefix="/auth", tags=["auth"])


class UserRole(str, Enum):
    ADMIN = "admin"
    AGENT = "agent"
    LEADER = "leader"
    CLIENT = "client"


class UserSignUp(BaseModel):
    email: EmailStr
    password: str = Field(
        ..., min_length=8, description="User password, minimum 8 characters"
    )
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Username, between 3-50 characters",
    )
    company_name: str = Field(
        ..., min_length=2, description="Company name, minimum 2 characters"
    )
    role: str = Field("client", description="User role, defaults to 'client'")
    department: Optional[str] = Field(None, description="Department within the company")

    @field_validator("password")
    def password_strength(cls, v):
        if not any(char.isdigit() for char in v):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in v):
            raise ValueError("Password must contain at least one uppercase letter")
        return v


class UserLogin(BaseModel):
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10, description="JWT refresh token")


@router.post("/signup")
async def sign_up(user_data: UserSignUp, supabase: Client = Depends(get_supabase)):
    try:
        # Check if email already exists in your users table
        check_response = (
            supabase.table("users")
            .select("email")
            .eq("email", user_data.email)
            .execute()
        )

        if check_response.data and len(check_response.data) > 0:
            raise HTTPException(status_code=400, detail="Email already registered")

        company_id = None

        # Check if company already exists
        check_company = (
            supabase.table("company_client")
            .select("*")
            .eq("name", user_data.company_name)
            .execute()
        )

        # If it does just set the company id
        if check_company.data:
            company_id = check_company.data[0]["company_id"]
        else:  # if not insert it and get whatever company id was created for it
            create_company = (
                supabase.table("company_client")
                .insert({"name": user_data.company_name})
                .execute()
            )
            if not create_company.data:
                raise HTTPException(status_code=500, detail="Failed to create company")
            company_id = create_company.data[0]["company_id"]

        # Create user in Supabase Auth
        auth_response = supabase.auth.sign_up(
            {"email": user_data.email, "password": user_data.password}
        )

        # Get the user ID from Supabase Auth
        user_id = auth_response.user.id

        # Create a record in your users table
        user_record = {
            "user_id": user_id,
            "username": user_data.username,
            "email": user_data.email,
            "role": user_data.role,
            "department": user_data.department,
            "company_id": company_id,
            # created_at will be handled by Supabase's default value
        }

        supabase.table("users").insert(user_record).execute()

        return {
            "message": "User created successfully",
            "user_id": user_id,
            "username": user_data.username,
            "role": user_data.role,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Registration failed: {str(e)}")


@router.post("/login")
async def login(credentials: UserLogin, supabase: Client = Depends(get_supabase)):
    try:
        # Authenticate user with Supabase Auth
        auth_response = supabase.auth.sign_in_with_password(
            {"email": credentials.email, "password": credentials.password}
        )

        user_id = auth_response.user.id

        # Get the user data from your table
        user_response = (
            supabase.table("users").select("*").eq("user_id", user_id).execute()
        )
        user_data = user_response.data[0] if user_response.data else {}

        # Create response data
        user_data_response = {
            "user": {
                "user_id": user_id,
                "username": user_data.get("username"),
                "email": user_data.get("email"),
                "role": user_data.get("role"),
                "department": user_data.get("department"),
            },
        }

        # Create response object with the JSON content
        response = JSONResponse(content=user_data_response)

        node_env = settings.NODE_ENV

        cookie_params = {
            "key": "access_token",
            "value": auth_response.session.access_token,
            "httponly": True,
            "domain": "localhost",
            "samesite": "lax",
            "max_age": 3600,
        }

        if node_env != "development":
            cookie_params["domain"] = ".callsight.tech"
            cookie_params["secure"] = True

        response.set_cookie(**cookie_params)

        refresh_cookie_params = {
            "key": "refresh_token",
            "value": auth_response.session.refresh_token,
            "httponly": True,
            "domain": "localhost",
            "samesite": "lax",
            "max_age": 7 * 24 * 3600,
        }

        if node_env != "development":
            cookie_params["domain"] = ".callsight.tech"
            refresh_cookie_params["secure"] = True

        response.set_cookie(**refresh_cookie_params)

        return response
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid credentials: {str(e)}")


@router.post("/logout")
async def logout(
    request: Request,
    supabase: Client = Depends(get_supabase),
):
    try:
        access_token = request.cookies.get("access_token")
        if not access_token:
            raise HTTPException(
                status_code=400, detail="Access token not found in cookies"
            )

        supabase.auth.admin.sign_out(jwt=access_token)

        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_access_token(
    request: Request, supabase: Client = Depends(get_supabase)
):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Refresh token not found")

        # Create a response object
        response = Response()

        # Refresh the session with Supabase
        auth_response = supabase.auth.refresh_session(refresh_token)

        node_env = settings.NODE_ENV

        cookie_params = {
            "key": "access_token",
            "value": auth_response.session.access_token,
            "httponly": True,
            "domain": "localhost",
            "samesite": "lax",
            "max_age": 3600,
        }

        if node_env != "development":
            cookie_params["domain"] = ".callsight.tech"
            cookie_params["secure"] = True

        response.set_cookie(**cookie_params)

        refresh_cookie_params = {
            "key": "refresh_token",
            "value": auth_response.session.refresh_token,
            "httponly": True,
            "domain": "localhost",
            "samesite": "lax",
            "max_age": 7 * 24 * 3600,
        }

        if node_env != "development":
            cookie_params["domain"] = ".callsight.tech"
            refresh_cookie_params["secure"] = True

        response.set_cookie(**refresh_cookie_params)

        return response
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token refresh failed: {str(e)}")


@router.get("/me")
async def get_current_user_profile(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    try:
        user_id = current_user.id
        response = supabase.table("users").select("*").eq("user_id", user_id).execute()

        if not response.data:
            raise HTTPException(status_code=404, detail="User profile not found")

        user_data = response.data[0]
        return {
            "user_id": user_data["user_id"],
            "username": user_data["username"],
            "email": user_data["email"],
            "role": user_data["role"],
            "department": user_data["department"],
            "created_at": user_data["created_at"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def check_user_role(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    """Check the user role"""
    user_id = current_user.id
    response = supabase.table("users").select("role").eq("user_id", user_id).execute()
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")
    return response.data[0]["role"]


async def check_admin_role(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    """Check if the current user has admin role"""
    user_id = current_user.id
    response = supabase.table("users").select("role").eq("user_id", user_id).execute()

    if not response.data or response.data[0]["role"] != "admin":
        raise HTTPException(
            status_code=403, detail="Not authorized. Admin role required."
        )
    return current_user


class UserUpdate(BaseModel):
    username: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        description="Username, between 3-50 characters",
    )
    email: Optional[EmailStr] = Field(None, description="User email address")
    role: Optional[str] = Field(None, description="User role")
    department: Optional[str] = Field(None, description="Department within the company")


@router.get("/users", dependencies=[Depends(check_admin_role)])
async def list_users(
    skip: int = 0, limit: int = 100, supabase: Client = Depends(get_supabase)
):
    """List all users - admin only endpoint"""
    response = (
        supabase.table("users").select("*").range(skip, skip + limit - 1).execute()
    )
    return {"users": response.data}


@router.get("/users/{user_id}", dependencies=[Depends(check_admin_role)])
async def get_user(user_id: str, supabase: Client = Depends(get_supabase)):
    """Get a specific user by ID - admin only endpoint"""
    response = supabase.table("users").select("*").eq("user_id", user_id).execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")

    return response.data[0]


@router.patch("/users/{user_id}", dependencies=[Depends(check_admin_role)])
async def update_user(
    user_id: str, user_data: UserUpdate, supabase: Client = Depends(get_supabase)
):
    """Update user data - admin only endpoint"""
    # Create dict with only the fields that were provided
    update_data = {k: v for k, v in user_data.dict().items() if v is not None}

    if not update_data:
        return {"message": "No fields to update"}

    response = (
        supabase.table("users").update(update_data).eq("user_id", user_id).execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")

    return {"message": "User updated successfully", "user": response.data[0]}


@router.get("/clients")
async def get_my_clients(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    """Get clients that the agent has worked with or all clients if admin"""
    try:
        user_id = current_user.id

        # Check user role
        role_response = (
            supabase.table("users").select("role").eq("user_id", user_id).execute()
        )
        if not role_response.data:
            raise HTTPException(status_code=404, detail="User not found")

        user_role = role_response.data[0]["role"]

        if user_role == UserRole.ADMIN:
            # Admin gets all clients
            clients_response = (
                supabase.table("users")
                .select("user_id, username, email, company_id")
                .eq("role", "client")
                .execute()
            )
            return {"clients": clients_response.data}
        elif user_role == UserRole.AGENT:
            # Get conversations this user participated in
            participant_response = (
                supabase.table("participants")
                .select("conversation_id")
                .eq("user_id", user_id)
                .execute()
            )

            if not participant_response.data:
                return {"clients": []}

            conversation_ids = [
                item["conversation_id"] for item in participant_response.data
            ]

            # Get other participants from these conversations
            other_participants = (
                supabase.table("participants")
                .select("user_id")
                .in_("conversation_id", conversation_ids)
                .neq("user_id", user_id)
                .execute()
            )

            if not other_participants.data:
                return {"clients": []}

            other_user_ids = list(
                set([item["user_id"] for item in other_participants.data])
            )

            # Get client info for these users
            clients_response = (
                supabase.table("users")
                .select("user_id, username, email, company_id")
                .in_("user_id", other_user_ids)
                .eq("role", "client")
                .execute()
            )

            return {"clients": clients_response.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
