from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from typing import List, Optional


from app.api.deps import get_current_user
from app.db.session import get_supabase
from app.api.routes.auth import check_user_role
from app.db.session import execute_query

from datetime import datetime
from dateutil.relativedelta import relativedelta

router = APIRouter(prefix="/topics", tags=["topics"])

@router.get("/")
async def get_topics(
    clients: List[str] = Query(default=[]),
    startDate: Optional[str] = Query(default=datetime.now().replace(day=1).strftime("%Y-%m-%d")),
    endDate: Optional[str] = Query(default=(datetime.now().replace(day=1) + relativedelta(months=1, days=-1)).strftime("%Y-%m-%d")),
    limit: int = Query(default=10),
    current_user=Depends(get_current_user),
    supabase: Client=Depends(get_supabase)
):
    user_id = current_user.id
    start_date = datetime.strptime(startDate, "%Y-%m-%d").date()
    end_date = datetime.strptime(endDate, "%Y-%m-%d").date()

    try:
        role = await check_user_role(current_user, supabase)

        if role == "admin":
            if not clients:
                query = """
                    SELECT t.topic AS topic, COUNT(DISTINCT c.conversation_id) AS amount  
                    FROM conversations c
                    INNER JOIN participants p ON c.conversation_id = p.conversation_id
                    INNER JOIN topics_conversations tc ON c.conversation_id = tc.conversation_id
                    INNER JOIN topics t ON tc.topic_id = t.topic_id
                    WHERE c.start_time BETWEEN $1 AND $2
                    GROUP BY t.topic_id
                    ORDER BY amount DESC
                    LIMIT $3
                """
                result = await execute_query(query, start_date, end_date, limit)
            else:
                query = """
                    SELECT t.topic AS topic, COUNT(DISTINCT c.conversation_id) AS amount  
                    FROM conversations c
                    INNER JOIN participants p ON c.conversation_id = p.conversation_id
                    INNER JOIN topics_conversations tc ON c.conversation_id = tc.conversation_id
                    INNER JOIN topics t ON tc.topic_id = t.topic_id
                    WHERE c.start_time BETWEEN $1 AND $2
                    AND p.user_id = ANY($3)
                    GROUP BY t.topic_id
                    ORDER BY amount DESC
                    LIMIT $4
                """
                result = await execute_query(query, start_date, end_date, clients, limit)
            return {"topics": result}

        elif role == "agent":
            if not clients:
                query = """
                    SELECT t.topic AS topic, COUNT(DISTINCT c.conversation_id) AS amount
                    FROM conversations c
                    INNER JOIN participants p ON c.conversation_id = p.conversation_id
                    INNER JOIN topics_conversations tc ON c.conversation_id = tc.conversation_id
                    INNER JOIN topics t ON tc.topic_id = t.topic_id
                    WHERE p.user_id = $1 AND c.start_time BETWEEN $2 AND $3
                    GROUP BY t.topic_id
                    ORDER BY amount DESC
                    LIMIT $4
                """
                result = await execute_query(query, user_id, start_date, end_date, limit)
            else:
                query = """
                    SELECT t.topic AS topic, COUNT(DISTINCT c.conversation_id) AS amount
                    FROM conversations c
                    INNER JOIN participants p ON c.conversation_id = p.conversation_id
                    INNER JOIN topics_conversations tc ON c.conversation_id = tc.conversation_id
                    INNER JOIN topics t ON tc.topic_id = t.topic_id
                    WHERE p.user_id = $1 AND c.start_time BETWEEN $2 AND $3
                    AND p.user_id = ANY($4)
                    GROUP BY t.topic_id
                    ORDER BY amount DESC
                    LIMIT $5
                """
                result = await execute_query(query, user_id, start_date, end_date, clients, limit)
            return {"topics": result}

        raise HTTPException(status_code=403, detail="Access denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))