from fastapi import Depends, HTTPException, Request, status
from supabase import Client

from app.db.session import get_supabase


async def get_current_user(
    request: Request,  # Add the request parameter to access cookies
    supabase: Client = Depends(get_supabase),
):
    """
    Validate access token from cookie and return user information.
    Used as a dependency for protected routes.
    """
    try:
        # Get token from the httpOnly cookie instead of Authorization header
        token = request.cookies.get("access_token")

        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication cookie not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get the user from the current session
        response = supabase.auth.get_user(token)

        return response.user
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Example of a protected route:
"""
@router.get("/protected")
async def protected_route(
    current_user = Depends(get_current_user)
):
    return {
        "message": "This is a protected route",
        "user_id": current_user.id,
        "email": current_user.email
    }
"""
