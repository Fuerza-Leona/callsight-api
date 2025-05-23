import io
import uuid
from datetime import datetime
from typing import Dict, Any, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def format_date(date_obj: datetime) -> str:
    """Format a date in a human-readable format."""
    return date_obj.strftime("%B %Y")


def create_monthly_report(
    company_name: str,
    start_date: datetime,
    end_date: datetime,
    summary_data: Dict[str, Any],
    topics_data: List[Dict[str, Any]],
    categories_data: List[Dict[str, Any]],
    ratings_data: List[Dict[str, Any]],
    emotions_data: Dict[str, float],
) -> bytes:
    """
    Create a PDF monthly report with the given data.

    Args:
        company_name: Name of the company
        start_date: Start date of the reporting period
        end_date: End date of the reporting period
        summary_data: Summary metrics
        topics_data: Topic distribution data
        categories_data: Categories data
        ratings_data: Rating distribution data
        emotions_data: Emotional sentiment data

    Returns:
        The generated PDF as bytes
    """
    # Create a buffer for the PDF
    buffer = io.BytesIO()

    # Create the PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72,
    )

    # Get styles
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    heading1_style = styles["Heading1"]
    normal_style = styles["Normal"]

    # Create a custom style for the header
    header_style = ParagraphStyle(
        "HeaderStyle", parent=heading1_style, fontSize=16, spaceAfter=12
    )

    # Create a list to hold the PDF elements
    elements = []

    # Add title and header
    elements.append(Paragraph("Reporte Mensual:", title_style))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Para: {company_name}", header_style))
    elements.append(
        Paragraph(
            f"Periodo {format_date(start_date)} - {format_date(end_date)}", header_style
        )
    )
    elements.append(Spacer(1, 24))

    # Add summary section
    elements.append(Paragraph("Resumen", heading1_style))
    elements.append(Spacer(1, 12))

    # Create a table for summary data
    summary_table_data = [
        ["Metrica", "Valor"],
        ["Llamadas totales", str(summary_data.get("total_calls", 0))],
        ["Duracion promedio", f"{summary_data.get('avg_duration', 0):.1f} minutes"],
        ["Satisfacción", f"{summary_data.get('avg_satisfaction', 0) * 100:.1f}%"],
    ]

    summary_table = Table(summary_table_data, colWidths=[250, 200])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.black),
                ("ALIGN", (0, 0), (1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(summary_table)
    elements.append(Spacer(1, 24))

    # Add topics section
    elements.append(Paragraph("Temas principales", heading1_style))
    elements.append(Spacer(1, 12))

    if topics_data:
        # Create a table for topics data
        topics_table_data = [["Tema", "Frequencia"]]
        for topic in topics_data[:5]:  # Show top 5 topics
            topics_table_data.append(
                [topic.get("topic", ""), str(topic.get("count", 0))]
            )

        topics_table = Table(topics_table_data, colWidths=[250, 200])
        topics_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (1, 0), colors.black),
                    ("ALIGN", (0, 0), (1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(topics_table)
    else:
        elements.append(
            Paragraph(
                "No hay datos de temas disponibles para este periodo.", normal_style
            )
        )

    elements.append(Spacer(1, 24))

    # Add emotions section
    elements.append(Paragraph("Analisis de sentimiento", heading1_style))
    elements.append(Spacer(1, 12))

    # Create a table for emotions data
    emotions_table_data = [
        ["Sentimiento", "Porcentaje"],
        ["Postitivo", f"{emotions_data.get('positive', 0) * 100:.1f}%"],
        ["Neutral", f"{emotions_data.get('neutral', 0) * 100:.1f}%"],
        ["Negativo", f"{emotions_data.get('negative', 0) * 100:.1f}%"],
    ]

    emotions_table = Table(emotions_table_data, colWidths=[250, 200])
    emotions_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
                ("TEXTCOLOR", (0, 0), (1, 0), colors.black),
                ("ALIGN", (0, 0), (1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]
        )
    )

    elements.append(emotions_table)
    elements.append(Spacer(1, 24))

    # Add ratings section if available
    if ratings_data:
        elements.append(Paragraph("Distribucion de ratings", heading1_style))
        elements.append(Spacer(1, 12))

        # Create a table for ratings data
        ratings_table_data = [["Rating", "Frequencia"]]
        for rating in ratings_data:
            ratings_table_data.append(
                [str(rating.get("rating", "")), str(rating.get("count", 0))]
            )

        ratings_table = Table(ratings_table_data, colWidths=[250, 200])
        ratings_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (1, 0), colors.black),
                    ("ALIGN", (0, 0), (1, 0), "CENTER"),
                    ("FONTNAME", (0, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (1, 0), 12),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        elements.append(ratings_table)
        elements.append(Spacer(1, 24))

    # Build the PDF
    doc.build(elements)

    # Get the PDF data
    pdf_data = buffer.getvalue()
    buffer.close()

    return pdf_data


async def save_report_to_storage(
    supabase,
    pdf_data: bytes,
    company_name: str,
    start_date: datetime,
    end_date: datetime,
    user_id: str,
) -> Dict[str, Any]:
    """
    Save the report to Supabase storage and create a record in the reports table.

    Args:
        supabase: Supabase client
        pdf_data: The PDF data to save
        company_name: Name of the company
        start_date: Start date of the reporting period
        end_date: End date of the reporting period
        user_id: ID of the user who generated the report

    Returns:
        Dictionary with the report information
    """
    report_id = str(uuid.uuid4())
    formatted_date = start_date.strftime("%Y-%m")
    file_name = f"{company_name.lower().replace(' ', '_')}_{formatted_date}.pdf"
    storage_path = f"reports/{report_id}/{file_name}"

    # Upload to Supabase storage
    try:
        supabase.storage.from_("reports").upload(
            storage_path, pdf_data, file_options={"content_type": "application/pdf"}
        )
    except Exception as upload_error:
        raise Exception(f"Failed to upload report to storage: {str(upload_error)}")

    # Get the public URL
    file_url = supabase.storage.from_("reports").get_public_url(storage_path)

    # Create a record in the reports table
    report_data = {
        "report_id": report_id,
        "name": f"Monthly Report - {company_name} - {formatted_date}",
        "created_by": user_id,
        "type": "pdf",
        "file_path": file_url,
    }

    db_response = supabase.table("reports").insert(report_data).execute()

    if not db_response.data:
        raise Exception("Failed to insert record into database")

    return {
        "report_id": report_id,
        "report_name": report_data["name"],
        "file_url": file_url,
        "created_at": datetime.now().isoformat(),
    }
