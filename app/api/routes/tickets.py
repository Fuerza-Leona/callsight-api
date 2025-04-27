import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional
from supabase import Client
from enum import Enum
from datetime import datetime

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_user_role, UserRole

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ------------------- Utility Endpoint -------------------
@router.get(
    "/companies",
    response_model=dict,
    summary="Get companies based on user role",
    description="Admins and agents get all companies; clients get only their company.",
)
async def get_user_companies(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        role = await check_user_role(current_user, supabase)

        if role in [UserRole.ADMIN, UserRole.AGENT]:
            companies = supabase.table("company_client").select("*").execute()
        else:
            companies = (
                supabase.table("users")
                .select("company_id,company_client(name)")
                .eq("user_id", current_user.id)
                .execute()
            )

        return {"companies": companies.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- Ticket List -------------------
@router.get(
    "/",
    response_model=dict,
    summary="Get user tickets",
    description="Returns tickets based on user's company_id instead of assigned_to or created_by.",
)
async def get_mine(
    company_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        role = await check_user_role(current_user, supabase)

        # Determine the correct company_id
        if role in [UserRole.ADMIN, UserRole.AGENT] and company_id:
            resolved_company_id = company_id
        else:
            company_response = (
                supabase.table("users")
                .select("company_id,company_client(name), company_client(logo)")
                .eq("user_id", current_user.id)
                .execute()
            )
            if not company_response.data:
                raise HTTPException(status_code=404, detail="Company not found")
            resolved_company_id = company_response.data[0]["company_id"]

        # Filter tickets by company_id and sort manually
        tickets_response = (
            supabase.table("support_tickets")
            .select("*")
            .eq("company_id", resolved_company_id)
            .execute()
        )

        tickets = sorted(
            tickets_response.data, key=lambda x: x["created_at"], reverse=True
        )

        return {"tickets": tickets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- Ticket Messages -------------------
@router.get(
    "/{ticket_id}/messages",
    response_model=dict,
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
            .select("*, users(user_id, role)")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        messages = sorted(messages_response.data, key=lambda x: x["created_at"])
        
        for message in messages:
            if message.get("users") and message["users"].get("role"):
                message["sender_role"] = message["users"]["role"]
            else:
                message["sender_role"] = "unknown"
            

        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- Ticket Creation -------------------


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"


class TicketCreate(BaseModel):
    subject: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10)
    status: Optional[TicketStatus] = (
        TicketStatus.OPEN
    )  # Se puede definir desde el inicio si se desea


@router.post(
    "/companies/{company_id}/tickets",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="Create support ticket",
    description="Creates a new support ticket for a specific company.",
)
async def create_ticket(
    company_id: str,
    ticket_data: TicketCreate,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        ticket_id = str(uuid.uuid4())

        ticket = {
            "ticket_id": ticket_id,
            "subject": ticket_data.subject,
            "description": ticket_data.description,
            "created_by": current_user.id,
            "company_id": company_id,
            "status": ticket_data.status,  # Usamos el status definido, o el default OPEN
        }

        result = supabase.table("support_tickets").insert(ticket).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to create ticket")

        return {"success": True, "ticket_id": ticket_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ------------------- Message Creation -------------------
class MessageCreate(BaseModel):
    message: str = Field(..., min_length=1)


@router.post(
    "/{ticket_id}/messages",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="Add message to ticket",
    description="Adds a new message to an existing support ticket.",
)
async def add_message(
    ticket_id: str,
    message_data: MessageCreate,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        # Validate ticket existence
        ticket = (
            supabase.table("support_tickets")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not ticket.data:
            raise HTTPException(status_code=404, detail="Ticket not found")

        message = {
            "message_id": str(uuid.uuid4()),
            "ticket_id": ticket_id,
            "sender_id": current_user.id,
            "message": message_data.message,
            "created_at": datetime.utcnow().isoformat(),
        }

        result = supabase.table("ticket_messages").insert(message).execute()

        if not result.data:
            raise HTTPException(status_code=500, detail="Failed to add message")

        return {"success": True, "message_id": result.data[0]["message_id"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # ------------------- Ticket Status Update -------------------


@router.put(
    "/{ticket_id}/status",
    response_model=dict,
    summary="Update ticket status",
    description="Updates the status of an existing support ticket.",
)
async def update_ticket_status(
    ticket_id: str,
    status: TicketStatus,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        # Validate ticket existence
        ticket = (
            supabase.table("support_tickets")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not ticket.data:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Check if the user is authorized to update the ticket status
        role = await check_user_role(current_user, supabase)
        if role == UserRole.CLIENT:
            # Clients can only update tickets they created or their company's tickets
            if ticket.data[0]["company_id"] != current_user.company_id:
                raise HTTPException(
                    status_code=403, detail="Not authorized to update this ticket"
                )

        # Update the ticket's status
        update_result = (
            supabase.table("support_tickets")
            .update({"status": status})
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not update_result.data:
            raise HTTPException(
                status_code=500, detail="Failed to update ticket status"
            )

        return {"success": True, "ticket_id": ticket_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
