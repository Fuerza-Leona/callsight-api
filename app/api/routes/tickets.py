import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import List, Optional
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
    description="Admins and agents get all companies; clients get only their company."
)
async def get_user_companies(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    try:
        role = await check_user_role(current_user, supabase)

        if role in [UserRole.ADMIN, UserRole.AGENT]:
            # Para administradores y agentes, obtener todas las empresas
            companies = supabase.table("company_client").select("*").execute()
        else:
            # Para clientes, obtener solo su empresa
            # El problema parece estar en esta consulta
            user_query = (
                supabase.table("users")
                .select("company_id")
                .eq("user_id", current_user.id)
                .single()
                .execute()
            )
            
            if user_query.data:
                company_id = user_query.data.get("company_id")
                if company_id:
                    # Ahora obtenemos los detalles de la empresa con el company_id
                    company_query = (
                        supabase.table("company_client")
                        .select("*")
                        .eq("company_id", company_id)
                        .execute()
                    )
                    companies = company_query
                else:
                    companies.data = []
            else:
                companies.data = []

        return {"companies": companies.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------- Ticket List -------------------
@router.get(
    "/",
    response_model=dict,
    summary="Get user tickets",
    description="Returns tickets based on user's company_id instead of assigned_to or created_by."
)
async def get_mine(
    company_id: Optional[str] = None,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        role = await check_user_role(current_user, supabase)

        # Determine the correct company_id
        if role in [UserRole.ADMIN, UserRole.AGENT] and company_id:
            resolved_company_id = company_id
        else:
            # Modificamos esta consulta para evitar el error
            user_response = (
                supabase.table("users")
                .select("company_id")  # Solo seleccionamos company_id
                .eq("user_id", current_user.id)
                .single()  # Obtenemos un solo registro
                .execute()
            )
            
            if not user_response.data:
                raise HTTPException(status_code=404, detail="User not found")
                
            resolved_company_id = user_response.data.get("company_id")
            
            if not resolved_company_id:
                raise HTTPException(status_code=404, detail="Company ID not found for user")

        # Filter tickets by company_id and sort manually
        tickets_response = (
            supabase.table("support_tickets")
            .select("*")
            .eq("company_id", resolved_company_id)
            .execute()
        )

        tickets = sorted(tickets_response.data, key=lambda x: x["created_at"], reverse=True)

        return {"tickets": tickets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ------------------- Ticket Messages -------------------
@router.get(
    "/{ticket_id}/messages",
    response_model=dict,
    summary="Get ticket messages",
    description="Returns all messages for a specific ticket ordered chronologically."
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
            .execute()
        )

        messages = sorted(messages_response.data, key=lambda x: x["created_at"])

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
    status: Optional[TicketStatus] = TicketStatus.OPEN  # Se puede definir desde el inicio si se desea


@router.post(
    "/companies/{company_id}/tickets",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
    summary="Create support ticket",
    description="Creates a new support ticket for a specific company."
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
    description="Adds a new message to an existing support ticket."
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
    description="Updates the status of an existing support ticket."
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
                raise HTTPException(status_code=403, detail="Not authorized to update this ticket")

        # Update the ticket's status
        update_result = supabase.table("support_tickets").update({"status": status}).eq("ticket_id", ticket_id).execute()

        if not update_result.data:
            raise HTTPException(status_code=500, detail="Failed to update ticket status")

        return {"success": True, "ticket_id": ticket_id, "status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------- Enhanced Ticket Filtering -------------------
@router.get(
    "/filter",
    response_model=dict,
    summary="Get filtered tickets",
    description="Returns tickets filtered by status and assignment for a specific company."
)
async def get_filtered_tickets(
    company_id: str,
    status: Optional[List[TicketStatus]] = Query(None),
    assigned_to_me: bool = Query(False),
    sort_by: str = Query("newest", description="Options: 'newest' or 'oldest'"),
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        role = await check_user_role(current_user, supabase)

        # Check user access to company
        if role == UserRole.CLIENT:
            # For clients, verify they belong to this company
            user_response = (
                supabase.table("users")
                .select("company_id")
                .eq("user_id", current_user.id)
                .single()
                .execute()
            )
            
            if not user_response.data or user_response.data.get("company_id") != company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, 
                    detail="Not authorized to view tickets for this company"
                )

        # Start building query - always filter by company_id
        query = supabase.table("support_tickets").select("*").eq("company_id", company_id)
        
        # Filter by status if provided
        if status and len(status) > 0:
            query = query.in_("status", [s.value for s in status])
        
        # Filter by assignment if requested
        if assigned_to_me:
            query = query.eq("assigned_to", current_user.id)
        
        # Execute the query
        tickets_response = query.execute()
        
        # Sort tickets based on sort_by parameter
        if sort_by == "newest":
            tickets = sorted(tickets_response.data, key=lambda x: x["created_at"], reverse=True)
        else:  # "oldest"
            tickets = sorted(tickets_response.data, key=lambda x: x["created_at"])

        return {"tickets": tickets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------- Ticket Assignment -------------------
@router.put(
    "/{ticket_id}/assign",
    response_model=dict,
    summary="Assign ticket to agent",
    description="Assigns a ticket to a specific agent. Only administrators can assign tickets."
)
async def assign_ticket(
    ticket_id: str,
    agent_id: str = Query(..., description="ID of the agent to assign the ticket to"),
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        # Check if user is an administrator
        role = await check_user_role(current_user, supabase)
        if role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can assign tickets"
            )
            
        # Validate ticket existence
        ticket = (
            supabase.table("support_tickets")
            .select("*")
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not ticket.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        # Validate that agent exists and is an agent
        agent_response = (
            supabase.table("users")
            .select("role")
            .eq("user_id", agent_id)
            .single()
            .execute()
        )
        
        if not agent_response.data:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Check if the user is an agent or admin
        agent_role = agent_response.data.get("role")
        if agent_role not in ["admin", "agent", "leader"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected user is not an agent or admin"
            )
            
        # Update the ticket with the assigned agent
        update_result = (
            supabase.table("support_tickets")
            .update({"assigned_to": agent_id})
            .eq("ticket_id", ticket_id)
            .execute()
        )

        if not update_result.data:
            raise HTTPException(status_code=500, detail="Failed to assign ticket")

        return {
            "success": True,
            "ticket_id": ticket_id,
            "assigned_to": agent_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ------------------- Get Agents List -------------------
@router.get(
    "/agents",
    response_model=dict,
    summary="Get all available agents",
    description="Returns a list of all agents who can be assigned to tickets."
)
async def get_agents(
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        # Check if user is authorized (admin or agent)
        role = await check_user_role(current_user, supabase)
        if role not in [UserRole.ADMIN, UserRole.AGENT]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view agents list"
            )
            
        # Get all users with role ADMIN or AGENT
        agents_response = (
            supabase.table("users")
            .select("user_id, username, email")
            .in_("role", ["admin", "agent"])
            .execute()
        )

        return {"agents": agents_response.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------- Get Ticket Details -------------------
@router.get(
    "/{ticket_id}",
    response_model=dict,
    summary="Get ticket details",
    description="Returns detailed information about a specific ticket."
)
async def get_ticket_details(
    ticket_id: str,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    try:
        # Retrieve the ticket
        ticket_response = (
            supabase.table("support_tickets")
            .select("*")
            .eq("ticket_id", ticket_id)
            .single()
            .execute()
        )

        if not ticket_response.data:
            raise HTTPException(status_code=404, detail="Ticket not found")
            
        ticket = ticket_response.data
        
        # Check if user has access to this ticket
        role = await check_user_role(current_user, supabase)
        
        if role == UserRole.CLIENT:
            # Clients can only view tickets from their company
            user_response = (
                supabase.table("users")
                .select("company_id")
                .eq("user_id", current_user.id)
                .single()
                .execute()
            )
            
            if not user_response.data or user_response.data.get("company_id") != ticket.get("company_id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not authorized to view this ticket"
                )
        
        # Get company information
        company_response = (
            supabase.table("company_client")
            .select("*")
            .eq("company_id", ticket.get("company_id"))
            .single()
            .execute()
        )
        
        # Get assigned agent information if assigned
        assigned_to = ticket.get("assigned_to")
        agent_info = None
        
        if assigned_to:
            agent_response = (
                supabase.table("users")
                .select("user_id, username, email")
                .eq("user_id", assigned_to)
                .single()
                .execute()
            )
            if agent_response.data:
                agent_info = agent_response.data
        
        # Get creator information
        creator_response = (
            supabase.table("users")
            .select("user_id, name, email")
            .eq("user_id", ticket.get("created_by"))
            .single()
            .execute()
        )
        
        creator_info = creator_response.data if creator_response.data else None
        
        return {
            "ticket": ticket,
            "company": company_response.data if company_response.data else None,
            "assigned_to": agent_info,
            "created_by": creator_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))