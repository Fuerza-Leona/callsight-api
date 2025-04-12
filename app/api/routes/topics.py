from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from typing import List, Optional
from app.api.deps import get_current_user
from app.db.session import get_supabase, execute_query
from app.api.routes.auth import check_user_role
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pydantic import BaseModel

router = APIRouter(prefix="/topics", tags=["topics"])


async def build_topics_query(
    start_date, end_date, role, user_id, clients, categories, limit
):
    base_query = """
        SELECT t.topic AS topic, COUNT(DISTINCT c.conversation_id) AS amount
        FROM conversations c
        INNER JOIN topics_conversations tc ON c.conversation_id = tc.conversation_id
        INNER JOIN topics t ON tc.topic_id = t.topic_id"""

    conditions = ["c.start_time BETWEEN %s AND %s"]
    params = [start_date, end_date]

    if role == "agent":
        base_query += """
        INNER JOIN participants p_agent ON c.conversation_id = p_agent.conversation_id"""
        conditions.append("p_agent.user_id = %s")
        params.append(user_id)

    if clients:
        base_query += """
        INNER JOIN participants p_client ON c.conversation_id = p_client.conversation_id"""
        conditions.append("p_client.user_id = ANY(%s::uuid[])")
        params.append(clients)

    if categories:
        base_query += """
        INNER JOIN company_client cc ON c.company_id = cc.company_id"""
        conditions.append("cc.category_id = ANY(%s::uuid[])")
        params.append(categories)

    if conditions:
        base_query += """
        WHERE """ + "\n        AND ".join(conditions)

    base_query += """
        GROUP BY t.topic_id
        ORDER BY amount DESC
        LIMIT %s
    """
    params.append(limit)
    return base_query, params


class TopicsRequest(BaseModel):
    clients: List[str] = []
    categories: List[str] = []
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
    categories = request.categories
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

    query, params = await build_topics_query(
        start_date, end_date, role, user_id, clients, categories, limit
    )
    try:
        result = await execute_query(query, *params)
        return {"topics": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")
