from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
import calendar
from dateutil.relativedelta import relativedelta

from app.db.session import get_supabase
from app.api.deps import get_current_user
from app.api.routes.auth import check_user_role
from app.services.report_service import (
    create_monthly_report,
    save_report_to_storage,
    create_file_name,
)


router = APIRouter(prefix="/reports", tags=["reports"])


async def find_existing_report(
    supabase: Client, report_name: str
) -> Optional[Dict[str, Any]]:
    """
    Find existing report for the same company and period.
    Returns the existing report record if found, None otherwise.
    """
    try:
        # Search for existing reports with same name
        response = (
            supabase.table("reports")
            .select("*")
            .eq("name", report_name)
            .limit(1)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception:
        # No existing report
        return None


async def cleanup_old_report(supabase: Client, old_report: Dict[str, Any]) -> None:
    """
    Clean up old report files and database records.
    """
    try:
        # Extract storage path from file_path URL
        file_url = old_report.get("file_path", "")
        if file_url:
            if "/reports/" in file_url:
                storage_path = file_url.split("/reports/", 1)[1]

                # Delete from storage
                try:
                    supabase.storage.from_("reports").remove(
                        [f"reports/{storage_path}"]
                    )
                except Exception:
                    pass

        # Delete database record
        supabase.table("reports").delete().eq(
            "report_id", old_report["report_id"]
        ).execute()

    except Exception:
        pass


class MonthlyReportRequest(BaseModel):
    month: Optional[int] = None
    year: Optional[int] = None
    company_id: Optional[str] = None


@router.post("/monthly")
async def generate_monthly_report(
    request: MonthlyReportRequest,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """
    Generate a monthly report PDF with key metrics:
    - Main topics
    - Sentiment analysis
    - Total calls
    - Average call duration
    - Satisfaction percentage
    - Rating distribution
    """
    try:
        # Check user role
        role = await check_user_role(current_user, supabase)
        if role not in ["admin", "agent"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Determine the reporting period
        now = datetime.now()
        if request.month and request.year:
            # Use specified month and year
            month = request.month
            year = request.year
        else:
            # Default to previous month
            previous_month = now - relativedelta(months=1)
            month = previous_month.month
            year = previous_month.year

        # Validate month
        if month < 1 or month > 12:
            raise HTTPException(
                status_code=400, detail="Invalid month. Must be between 1 and 12"
            )

        # Create date range for the report
        start_date = datetime(year, month, 1)

        # Last day of the month
        _, last_day = calendar.monthrange(year, month)
        end_date = datetime(year, month, last_day, 23, 59, 59)

        # Format dates for API calls
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Get company information if company_id is provided
        if request.company_id:
            company_response = (
                supabase.table("company_client")
                .select("name")
                .eq("company_id", request.company_id)
                .execute()
            )
            if not company_response.data:
                raise HTTPException(status_code=404, detail="Company not found")
            company_name = company_response.data[0]["name"]

            # Filter parameters for all data calls
            filter_params = {
                "clients": [],
                "categories": [],
                "startDate": start_date_str,
                "endDate": end_date_str,
            }

            # Add company_id to clients if specified
            if request.company_id:
                # Get users for this company
                users_response = (
                    supabase.table("users")
                    .select("user_id")
                    .eq("company_id", request.company_id)
                    .execute()
                )
                if users_response.data:
                    filter_params["clients"] = [
                        user["user_id"] for user in users_response.data
                    ]
        else:
            # If no company specified, use a generic name
            company_name = "All Companies"

            # Filter parameters for all data calls
            filter_params = {
                "clients": [],
                "categories": [],
                "startDate": start_date_str,
                "endDate": end_date_str,
            }

        existing_filename = create_file_name(company_name, start_date)
        existing_report = await find_existing_report(supabase, existing_filename)

        if existing_report:
            print("Existing report found! Cleaning up old report...")
            await cleanup_old_report(supabase, existing_report)

        # Gather all required data
        # 1. Get summary data
        summary_response = supabase.rpc(
            "build_conversations_summary",
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "user_role": role,
                "id": current_user.id,
                "clients": filter_params["clients"]
                if filter_params["clients"]
                else None,
                "categories": filter_params["categories"]
                if filter_params["categories"]
                else None,
            },
        ).execute()

        summary_data = summary_response.data[0] if summary_response.data else {}

        # 2. Get topics data
        topics_response = supabase.rpc(
            "build_topics_query",
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "user_role": role,
                "id": current_user.id,
                "clients": filter_params["clients"]
                if filter_params["clients"]
                else None,
                "categories": filter_params["categories"]
                if filter_params["categories"]
                else None,
                "limit_count": 10,  # Get top 10 topics
            },
        ).execute()

        topics_data = topics_response.data if topics_response.data else []

        # 3. Get categories data
        categories_response = supabase.rpc(
            "build_conversations_categories_query",
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "user_role": role,
                "id": current_user.id,
                "clients": filter_params["clients"]
                if filter_params["clients"]
                else None,
                "categories": filter_params["categories"]
                if filter_params["categories"]
                else None,
            },
        ).execute()

        categories_data = categories_response.data if categories_response.data else []

        # 4. Get ratings data
        ratings_response = supabase.rpc(
            "build_conversations_ratings_query",
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "user_role": role,
                "id": current_user.id,
                "clients": filter_params["clients"]
                if filter_params["clients"]
                else None,
                "categories": filter_params["categories"]
                if filter_params["categories"]
                else None,
            },
        ).execute()

        ratings_data = ratings_response.data if ratings_response.data else []

        # 5. Get emotions data
        emotions_response = supabase.rpc(
            "build_client_emotions_query",
            {
                "start_date": start_date_str,
                "end_date": end_date_str,
                "user_role": role,
                "id": current_user.id,
                "clients": filter_params["clients"]
                if filter_params["clients"]
                else None,
                "categories": filter_params["categories"]
                if filter_params["categories"]
                else None,
            },
        ).execute()

        emotions_data = {}
        if emotions_response.data and len(emotions_response.data) > 0:
            row = emotions_response.data[0]
            emotions_data = {
                "positive": row.get("positive", 0),
                "negative": row.get("negative", 0),
                "neutral": row.get("neutral", 0),
            }
        else:
            emotions_data = {"positive": 0, "negative": 0, "neutral": 0}

        # Generate the PDF report
        pdf_data = create_monthly_report(
            company_name,
            start_date,
            end_date,
            summary_data,
            topics_data,
            categories_data,
            ratings_data,
            emotions_data,
        )

        # Save the report to storage and database
        report_info = await save_report_to_storage(
            supabase, pdf_data, company_name, start_date, end_date, current_user.id
        )

        return {
            "success": True,
            "report": report_info,
            "period": {
                "month": month,
                "year": year,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate report: {str(e)}"
        )


@router.get("/")
async def list_reports(
    limit: int = 10,
    offset: int = 0,
    current_user=Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """List all reports generated by the current user"""
    try:
        # Get the reports
        response = (
            supabase.table("reports")
            .select("*")
            .eq("created_by", current_user.id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return {"reports": response.data}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch reports: {str(e)}"
        )
