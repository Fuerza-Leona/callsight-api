from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from typing import List, Optional
from app.api.deps import get_current_user
from app.db.session import get_supabase
from app.api.routes.auth import check_user_role
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel

router = APIRouter(prefix="/topics", tags=["topics"])


class TopicsRequest(BaseModel):
    clients: List[str] = []
    agents: List[str] = []
    companies: List[str] = []
    startDate: Optional[str] = datetime.now().replace(day=1).strftime("%Y-%m-%d")
    endDate: Optional[str] = (
        datetime.now().replace(day=1) + relativedelta(months=1, days=-1)
    ).strftime("%Y-%m-%d")
    limit: int = 10


@router.post("/")
async def get_topics(
    request: TopicsRequest,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    agents = request.agents
    companies = request.companies
    startDate = request.startDate
    endDate = request.endDate
    limit = request.limit

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    user_id = current_user.id
    role = await check_user_role(current_user, supabase)

    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        response = supabase.rpc(
            "new_build_topics_query",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": role,
                "id": user_id,
                "clients": clients if clients else None,
                "agents": agents if agents else None,
                "companies": companies if companies else None,
                "limit_count": limit,
            },
        ).execute()
        return {"topics": response.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


@router.post("/insights")
async def get_topics_insights(
    request: TopicsRequest,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    clients = request.clients
    agents = request.agents
    companies = request.companies
    startDate = request.startDate
    endDate = request.endDate
    limit = request.limit

    try:
        start_date = datetime.strptime(startDate, "%Y-%m-%d").date()
        end_date = datetime.strptime(endDate, "%Y-%m-%d").date()
        if start_date > end_date:
            raise ValueError("Start date cannot be after end date")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    user_id = current_user.id
    role = await check_user_role(current_user, supabase)

    if role not in ["admin", "agent"]:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        response = supabase.rpc(
            "new_build_topics_query",
            {
                "start_date": startDate,
                "end_date": endDate,
                "user_role": "admin",
                "id": user_id,
                "clients": clients if clients else None,
                "agents": agents if agents else None,
                "companies": companies if companies else None,
                "limit_count": limit,
            },
        ).execute()
        return {"topics": response.data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
