import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from supabase import Client
from enum import Enum

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_user_role, UserRole

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get(
    "/",
    response_model=dict,
    responses={
        200: {"description": "List of tickets filtered by user role"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
    summary="Get user tickets",
    description="Returns tickets based on user role: agents see tickets assigned to them, clients see tickets they created, admins and leaders see all tickets.",
)
async def get_mine(
    current_user=Depends(get_current_user), supabase: Client = Depends(get_supabase)
):
    """Get tickets for the currently authorized user, depending on the role"""
    try:
        user_id = current_user.id
        role = await check_user_role(current_user, supabase)

        tickets_response = None

        if (
            role == UserRole.AGENT
        ):  # If agent, get tickets based on assigned_to. If user, created_by. Admins and leaders see all tickets.
            tickets_response = (
                supabase.table("support_tickets")
                .select("*")
                .eq("assigned_to", user_id)
                .order_by("created_at", options={"ascending": False})
                .execute()
            )
        elif role == UserRole.CLIENT:
            tickets_response = (
                supabase.table("support_tickets")
                .select("*")
                .eq("created_by", user_id)
                .order_by("created_at", options={"ascending": False})
                .execute()
            )
        else:
            tickets_response = (
                supabase.table("support_tickets")
                .select("*")
                .order_by("created_at", options={"ascending": False})
                .execute()
            )

        return {"tickets": tickets_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{ticket_id}/messages",
    response_model=dict,
    responses={
        200: {"description": "List of messages for the ticket"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Ticket not found"},
        500: {"description": "Internal server error"},
    },
    summary="Get ticket messages",
    description="Returns all messages for a specific ticket ordered chronologically.",
)
async def get_ticket_messages(
    ticket_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        messages_response = (
            supabase.table("ticket_messages")
            .select("*")
            .eq("ticket_id", ticket_id)
            .order_by("created_at", options={"ascending": True})
            .execute()
        )

        return {"messages": messages_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10)
    assigned_to: Optional[str] = None


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    responses={
        201: {"description": "Ticket created successfully"},
        400: {"description": "Bad request - invalid data"},
        401: {"description": "Unauthorized - authentication required"},
        500: {"description": "Internal server error"},
    },
    summary="Create support ticket",
    description="Creates a new support ticket with the specified subject and description.",
)
async def create_ticket(
    ticket_data: TicketCreate,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Create a new support ticket"""
    try:
        # Generate ticket ID
        ticket_id = str(uuid.uuid4())

        # Create ticket record
        ticket = {
            "ticket_id": ticket_id,
            "subject": ticket_data.subject,
            "description": ticket_data.description,
            "created_by": current_user.id,
            "assigned_to": ticket_data.assigned_to,
            "status": TicketStatus.OPEN,
        }

        result = supabase.table("support_tickets").insert(ticket).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create ticket")

        return {"success": True, "ticket_id": ticket_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1)


@router.post(
    "/{ticket_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    responses={
        201: {"description": "Message added successfully"},
        400: {"description": "Bad request - invalid data"},
        401: {"description": "Unauthorized - authentication required"},
        404: {"description": "Ticket not found"},
        500: {"description": "Internal server error"},
    },
    summary="Add message to ticket",
    description="Adds a new message to an existing support ticket.",
)
async def add_message(
    ticket_id: str,
    message_data: MessageCreate,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Add a message to an existing ticket"""
    try:
        # Check if ticket exists
        ticket = (
            supabase.table("support_tickets")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not ticket.data:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Create message
        message = {
            "message_id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "sender_id": current_user.id,
            "message": message_data.message,
        }

        result = supabase.table("ticket_messages").insert(message).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to add message")

        return {"success": True, "message_id": result.data[0]["message_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
