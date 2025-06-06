import io
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import seaborn as sns
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY


class ReportTheme(Enum):
    """Report theme configurations"""

    CORPORATE = "corporate"
    MODERN = "modern"
    MINIMAL = "minimal"


@dataclass
class ReportConfig:
    theme: ReportTheme = ReportTheme.CORPORATE
    include_charts: bool = True
    include_insights: bool = True
    include_recommendations: bool = True
    chart_style: str = "seaborn-v0_8"
    color_palette: List[str] = None
    logo_path: Optional[str] = None

    def __post_init__(self):
        if self.color_palette is None:
            self.color_palette = ["#2E86AB", "#A23B72", "#F18F01", "#C73E1D", "#6A994E"]


class SpanishTexts:
    """Spanish text constants"""

    MONTHLY_REPORT = "Reporte Mensual de Análisis"
    FOR_COMPANY = "Para"
    PERIOD = "Periodo"
    SUMMARY = "Resumen Ejecutivo"
    KEY_METRICS = "Métricas Clave"
    TOTAL_CALLS = "Llamadas Totales"
    AVG_DURATION = "Duración Promedio"
    SATISFACTION = "Satisfacción del Cliente"
    MAIN_TOPICS = "Temas Principales"
    SENTIMENT_ANALYSIS = "Análisis de Sentimiento"
    RATING_DISTRIBUTION = "Distribución de Calificaciones"
    INSIGHTS = "Insights Clave"
    RECOMMENDATIONS = "Recomendaciones"
    TRENDS = "Tendencias del Período"
    PERFORMANCE_INDICATORS = "Indicadores de Rendimiento"

    # Sentiments
    POSITIVE = "Positivo"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negativo"

    # Table headers
    METRIC = "Métrica"
    VALUE = "Valor"
    TOPIC = "Tema"
    FREQUENCY = "Frecuencia"
    SENTIMENT = "Sentimiento"
    PERCENTAGE = "Porcentaje"
    RATING = "Calificación"

    # Units
    MINUTES = "minutos"
    CALLS = "llamadas"

    # Insights hardcodeados
    TOP_TOPIC_INSIGHT = "El tema más discutido fue '{topic}' con {count} menciones"
    SATISFACTION_INSIGHT = "La satisfacción promedio fue del {percent:.1f}%"
    SENTIMENT_INSIGHT = "El {percent:.1f}% de las interacciones fueron {sentiment}"
    DURATION_INSIGHT = "La duración promedio de llamadas fue {duration:.1f} minutos"


class ChartGenerator:
    def __init__(self, config: ReportConfig):
        self.config = config
        plt.style.use("seaborn-v0_8-whitegrid")
        sns.set_palette(config.color_palette)

    def _setup_chart_style(self, fig, ax):
        """Apply consistent styling to charts"""
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E0E0E0")
        ax.spines["bottom"].set_color("#E0E0E0")
        ax.grid(True, alpha=0.3)
        fig.patch.set_facecolor("white")

    def create_sentiment_donut_chart(self, emotions_data: Dict[str, float]) -> bytes:
        """Create a modern donut chart for sentiment analysis"""
        total = sum(emotions_data.values())
        if total == 0:
            return self._create_no_data_chart("No hay datos de sentimiento disponibles")

        fig, ax = plt.subplots(figsize=(6, 10))

        labels = [SpanishTexts.POSITIVE, SpanishTexts.NEUTRAL, SpanishTexts.NEGATIVE]
        values = [
            emotions_data.get("positive", 0) * 100,
            emotions_data.get("neutral", 0) * 100,
            emotions_data.get("negative", 0) * 100,
        ]
        colors = ["#6A994E", "#F18F01", "#C73E1D"]

        # Create donut chart
        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            colors=colors,
            autopct="%1.1f%%",
            startangle=90,
            pctdistance=0.85,
            wedgeprops=dict(width=0.5, edgecolor="white", linewidth=2),
        )

        # Styling
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontweight("bold")
            autotext.set_fontsize(12)

        for text in texts:
            text.set_fontsize(11)
            text.set_fontweight("600")

        ax.set_title("Análisis de Sentimiento", fontsize=16, fontweight="bold", pad=20)

        # Add center text
        centre_circle = plt.Circle((0, 0), 0.70, fc="white")
        fig.gca().add_artist(centre_circle)

        plt.tight_layout()

        # Convert to bytes
        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        chart_bytes = buffer.getvalue()
        buffer.close()
        plt.close()

        return chart_bytes

    def create_topics_bar_chart(self, topics_data: List[Dict[str, Any]]) -> bytes:
        """Create a horizontal bar chart for topics"""
        if not topics_data:
            return self._create_no_data_chart("No hay datos de temas disponibles")

        fig, ax = plt.subplots(figsize=(10, 6))

        # Get top 8 topics
        top_topics = topics_data[:8]
        topics = [topic.get("topic", "N/A") for topic in reversed(top_topics)]
        counts = [topic.get("amount", 0) for topic in reversed(top_topics)]

        # Create horizontal bar chart
        bars = ax.barh(topics, counts, color=self.config.color_palette[0], alpha=0.8)

        # Add value labels on bars
        for i, (bar, count) in enumerate(zip(bars, counts)):
            width = bar.get_width()
            ax.text(
                width + max(counts) * 0.01,
                bar.get_y() + bar.get_height() / 2,
                f"{count}",
                ha="left",
                va="center",
                fontweight="bold",
            )

        ax.set_xlabel("Frecuencia de Menciones", fontsize=12, fontweight="600")
        ax.set_title("Temas Más Discutidos", fontsize=16, fontweight="bold", pad=20)

        self._setup_chart_style(fig, ax)
        max_count = max(counts) if counts else 1
        ax.set_xlim(0, max_count * 1.15)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        chart_bytes = buffer.getvalue()
        buffer.close()
        plt.close()

        return chart_bytes

    def create_ratings_distribution_chart(
        self, ratings_data: List[Dict[str, Any]]
    ) -> bytes:
        """Create a modern bar chart for ratings distribution"""
        if not ratings_data:
            return self._create_no_data_chart(
                "No hay datos de calificaciones disponibles"
            )

        fig, ax = plt.subplots(figsize=(6, 8))

        ratings = [str(rating.get("rating", "")) for rating in ratings_data]
        counts = [rating.get("count", 0) for rating in ratings_data]

        # Color gradient based on rating
        colors_map = {
            "1": "#C73E1D",
            "2": "#F18F01",
            "3": "#F7B801",
            "4": "#A7C957",
            "5": "#6A994E",
        }
        bar_colors = [
            colors_map.get(rating, self.config.color_palette[0]) for rating in ratings
        ]

        bars = ax.bar(
            ratings, counts, color=bar_colors, alpha=0.8, edgecolor="white", linewidth=2
        )

        # Add value labels on top of bars
        for bar, count in zip(bars, counts):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + max(counts) * 0.01,
                f"{count}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

        ax.set_xlabel("Calificación", fontsize=12, fontweight="600")
        ax.set_ylabel("Número de Llamadas", fontsize=12, fontweight="600")
        ax.set_title(
            "Distribución de Calificaciones", fontsize=16, fontweight="bold", pad=20
        )

        self._setup_chart_style(fig, ax)
        ax.set_ylim(0, max(counts) * 1.15)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        chart_bytes = buffer.getvalue()
        buffer.close()
        plt.close()

        return chart_bytes

    def create_kpi_dashboard(self, summary_data: Dict[str, Any]) -> bytes:
        """Create a KPI dashboard visualization"""
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(12, 12))
        fig.suptitle(
            "Dashboard de Métricas Clave", fontsize=18, fontweight="bold", y=0.95
        )

        # Total calls gauge
        conversation_count = summary_data.get("conversation_count", 0)
        self._create_kpi_box(
            ax1,
            conversation_count,
            "Llamadas\nTotales",
            self.config.color_palette[0],
            max_value=1000,
        )

        # Average duration gauge
        average_minutes = summary_data.get("average_minutes", 0)
        self._create_kpi_box(
            ax2,
            f"{average_minutes:.1f}",
            "Duración\nPromedio (min)",
            self.config.color_palette[1],
            max_value=60,
        )

        # Satisfaction gauge
        satisfaction_raw = summary_data.get("avg_satisfaction", 0)
        satisfaction_display = f"{satisfaction_raw * 100:.1f}%"
        self._create_kpi_box(
            ax3,
            satisfaction_display,
            "Satisfacción\nPromedio",
            self.config.color_palette[2],
            max_value=1.0,
        )

        # Response time (mock data for example)
        response_time = summary_data.get("avg_response_time", 45)
        self._create_kpi_box(
            ax4,
            f"{response_time:.0f}s",
            "Tiempo de\nRespuesta",
            self.config.color_palette[3],
            120,
        )

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        chart_bytes = buffer.getvalue()
        buffer.close()
        plt.close()

        return chart_bytes

    def _create_kpi_box(self, ax, value, label, color, max_value=None):
        """Create a KPI box visualization"""

        # Extract numeric value
        if isinstance(value, str):
            import re

            numeric_match = re.search(r"[\d.]+", value)
            if numeric_match:
                numeric_value = float(numeric_match.group())
                # If it's a percentage, convert back to decimal
                if "%" in value:
                    numeric_value = numeric_value / 100
            else:
                numeric_value = 0
        else:
            numeric_value = float(value) if value else 0

        # Create half-donut gauge
        if max_value and numeric_value > 0:
            # Calculate fill percentage
            fill_percentage = min(numeric_value / max_value, 1.0)

            # Create background arc (gray)
            theta1, theta2 = 0, 180  # Half circle
            background_wedge = patches.Wedge(
                (0.5, 0.3),
                0.35,
                theta1,
                theta2,
                width=0.15,
                facecolor="#E5E5E5",
                transform=ax.transAxes,
            )
            ax.add_patch(background_wedge)

            # Create filled arc based on percentage
            fill_wedge = patches.Wedge(
                (0.5, 0.3),
                0.35,
                theta2 * (1 - fill_percentage),
                theta2,
                width=0.15,
                facecolor=color,
                alpha=0.8,
                transform=ax.transAxes,
            )
            ax.add_patch(fill_wedge)

        # Value text
        ax.text(
            0.5,
            0.7,
            str(value),
            ha="center",
            va="center",
            fontsize=24,
            fontweight="bold",
            color=color,
            transform=ax.transAxes,
        )

        # Label text
        ax.text(
            0.5,
            0.3,
            label,
            ha="center",
            va="center",
            fontsize=12,
            fontweight="600",
            transform=ax.transAxes,
        )

        # Add border
        rect = patches.Rectangle(
            (0.1, 0.1),
            0.8,
            0.8,
            linewidth=2,
            edgecolor=color,
            facecolor="none",
            transform=ax.transAxes,
        )
        ax.add_patch(rect)

        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

    def _create_no_data_chart(self, message: str) -> bytes:
        """Create a placeholder chart for when no data is available"""
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(
            0.5,
            0.5,
            message,
            ha="center",
            va="center",
            fontsize=14,
            transform=ax.transAxes,
        )
        ax.axis("off")

        buffer = io.BytesIO()
        plt.savefig(
            buffer,
            format="png",
            dpi=300,
            bbox_inches="tight",
            facecolor="white",
            edgecolor="none",
        )
        buffer.seek(0)
        chart_bytes = buffer.getvalue()
        buffer.close()
        plt.close()

        return chart_bytes


class InsightsGenerator:
    """Generate actionable insights from data"""

    @staticmethod
    def generate_insights(
        summary_data: Dict[str, Any],
        topics_data: List[Dict[str, Any]],
        emotions_data: Dict[str, float],
        ratings_data: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate key insights from the data"""
        insights = []

        # Topic insights
        if topics_data:
            top_topic = topics_data[0]
            insights.append(
                SpanishTexts.TOP_TOPIC_INSIGHT.format(
                    topic=top_topic.get("topic", "N/A"),
                    count=top_topic.get("amount", 0),
                )
            )

        # Satisfaction insights
        satisfaction = summary_data.get("avg_satisfaction", 0) * 100
        insights.append(SpanishTexts.SATISFACTION_INSIGHT.format(percent=satisfaction))

        # Sentiment insights
        dominant_sentiment = max(emotions_data.items(), key=lambda x: x[1])
        sentiment_name = {
            "positive": SpanishTexts.POSITIVE.lower(),
            "neutral": SpanishTexts.NEUTRAL.lower(),
            "negative": SpanishTexts.NEGATIVE.lower(),
        }.get(dominant_sentiment[0], dominant_sentiment[0])

        insights.append(
            SpanishTexts.SENTIMENT_INSIGHT.format(
                percent=dominant_sentiment[1] * 100, sentiment=sentiment_name
            )
        )

        # Duration insights
        duration = summary_data.get("average_minutes", 0)
        insights.append(SpanishTexts.DURATION_INSIGHT.format(duration=duration))

        # Performance insights
        if satisfaction > 80:
            insights.append(
                "El nivel de satisfacción del cliente está por encima del promedio de la industria"
            )
        elif satisfaction < 60:
            insights.append("Se recomienda revisar los procesos de atención al cliente")

        # Call volume insights
        conversation_count = summary_data.get("conversation_count", 0)
        if conversation_count > 1000:
            insights.append(
                "Alto volumen de llamadas indica una demanda robusta del servicio"
            )

        return insights

    @staticmethod
    def generate_recommendations(
        summary_data: Dict[str, Any],
        emotions_data: Dict[str, float],
        ratings_data: List[Dict[str, Any]],
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        satisfaction = summary_data.get("avg_satisfaction", 0) * 100
        negative_sentiment = emotions_data.get("negative", 0) * 100

        # Satisfaction-based recommendations
        if satisfaction < 70:
            recommendations.append(
                "Implementar programas de capacitación adicional para mejorar la satisfacción del cliente"
            )

        if negative_sentiment > 30:
            recommendations.append(
                "Revisar y optimizar los scripts de atención para reducir sentimientos negativos"
            )

        # Duration-based recommendations
        average_minutes = summary_data.get("average_minutes", 0)
        if average_minutes > 10:
            recommendations.append(
                "Considerar herramientas de automatización para reducir tiempo de resolución"
            )
        elif average_minutes < 3:
            recommendations.append(
                "Verificar que se está brindando suficiente atención a cada consulta"
            )

        # Rating-based recommendations
        if ratings_data:
            low_ratings = sum(
                r.get("count", 0) for r in ratings_data if int(r.get("rating", 5)) <= 2
            )
            total_ratings = sum(r.get("count", 0) for r in ratings_data)

            if low_ratings / max(total_ratings, 1) > 0.2:
                recommendations.append(
                    "Implementar un sistema de seguimiento para llamadas con calificaciones bajas"
                )

        # General recommendations
        recommendations.extend(
            [
                "Establecer métricas de seguimiento mensual para identificar tendencias",
                "Considerar la implementación de encuestas post-llamada para obtener feedback más detallado",
                "Analizar los temas más frecuentes para crear recursos de autoservicio",
            ]
        )

        return recommendations[:5]  # Limit to top 5 recommendations


def format_date(date_obj: datetime, main: bool = True) -> str:
    """Format a date in Spanish format."""
    months = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }
    return (
        f"{months[date_obj.month]} {date_obj.year}"
        if main
        else f"{date_obj.day} de {months[date_obj.month]} del {date_obj.year}"
    )


class ReportGenerator:
    """Enhanced report generator with modern styling and charts"""

    def __init__(self, config: ReportConfig = None):
        self.config = config or ReportConfig()
        self.chart_generator = ChartGenerator(self.config)

    def create_monthly_report(
        self,
        company_name: str,
        start_date: datetime,
        end_date: datetime,
        summary_data: Dict[str, Any],
        topics_data: List[Dict[str, Any]],
        categories_data: List[Dict[str, Any]],
        ratings_data: List[Dict[str, Any]],
        emotions_data: Dict[str, float],
    ) -> bytes:
        """Create an enhanced PDF monthly report"""

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2.5 * cm,
            bottomMargin=2 * cm,
        )

        formatted_date = start_date.strftime("%Y-%m")
        doc.title = f"Reporte Mensual - {company_name} - {formatted_date}"

        # Enhanced styles
        styles = self._create_enhanced_styles()
        elements = []

        # Title page
        elements.extend(
            self._create_title_page(company_name, start_date, end_date, styles)
        )
        elements.append(PageBreak())

        # Executive summary with KPI dashboard
        if self.config.include_charts:
            elements.extend(self._create_executive_summary(summary_data, styles))
            elements.append(PageBreak())

        # Detailed metrics section
        elements.extend(
            self._create_detailed_metrics(
                summary_data, topics_data, emotions_data, ratings_data, styles
            )
        )

        # Insights and recommendations
        if self.config.include_insights:
            elements.append(PageBreak())
            elements.extend(
                self._create_insights_section(
                    summary_data, topics_data, emotions_data, ratings_data, styles
                )
            )

        # Build PDF
        doc.build(elements)

        pdf_data = buffer.getvalue()
        buffer.close()

        return pdf_data

    def _create_enhanced_styles(self):
        """Create enhanced styles for the report"""
        styles = getSampleStyleSheet()

        # Custom title style
        styles.add(
            ParagraphStyle(
                name="CustomTitle",
                parent=styles["Title"],
                fontSize=28,
                textColor=colors.HexColor("#2E86AB"),
                spaceAfter=30,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            )
        )

        # Enhanced heading styles
        styles.add(
            ParagraphStyle(
                name="Heading1Enhanced",
                parent=styles["Heading1"],
                fontSize=18,
                textColor=colors.HexColor("#2E86AB"),
                spaceAfter=15,
                spaceBefore=20,
                fontName="Helvetica-Bold",
                borderWidth=0,
                borderColor=colors.HexColor("#2E86AB"),
                borderPadding=5,
            )
        )

        styles.add(
            ParagraphStyle(
                name="Heading2Enhanced",
                parent=styles["Heading2"],
                fontSize=14,
                textColor=colors.HexColor("#A23B72"),
                spaceAfter=10,
                spaceBefore=15,
                fontName="Helvetica-Bold",
            )
        )

        # Enhanced normal style
        styles.add(
            ParagraphStyle(
                name="NormalEnhanced",
                parent=styles["Normal"],
                fontSize=11,
                textColor=colors.HexColor("#333333"),
                spaceAfter=8,
                alignment=TA_JUSTIFY,
                fontName="Helvetica",
            )
        )

        # Insight style
        styles.add(
            ParagraphStyle(
                name="InsightStyle",
                parent=styles["Normal"],
                fontSize=11,
                textColor=colors.HexColor("#2E86AB"),
                spaceAfter=8,
                leftIndent=20,
                bulletIndent=10,
                fontName="Helvetica",
            )
        )

        return styles

    def _create_title_page(
        self, company_name: str, start_date: datetime, end_date: datetime, styles
    ) -> List:
        """Create an attractive title page"""
        elements = []

        # Main title
        elements.append(Spacer(1, 2 * inch))
        elements.append(Paragraph(SpanishTexts.MONTHLY_REPORT, styles["CustomTitle"]))
        elements.append(Spacer(1, 0.5 * inch))

        # Company info
        elements.append(
            Paragraph(
                f"<b>{SpanishTexts.FOR_COMPANY}:</b> {company_name}",
                styles["Heading1Enhanced"],
            )
        )
        elements.append(
            Paragraph(
                f"<b>{SpanishTexts.PERIOD}:</b> {format_date(start_date)}",
                styles["Heading2Enhanced"],
            )
        )

        elements.append(Spacer(1, 1 * inch))

        # Generated date
        elements.append(
            Paragraph(
                f"Generado el: {format_date(datetime.now(), False)}",
                styles["NormalEnhanced"],
            )
        )

        return elements

    def _create_executive_summary(self, summary_data: Dict[str, Any], styles) -> List:
        """Create executive summary with KPI dashboard"""
        elements = []

        elements.append(Paragraph(SpanishTexts.SUMMARY, styles["Heading1Enhanced"]))
        elements.append(Spacer(1, 12))

        # KPI Dashboard chart
        if self.config.include_charts:
            kpi_chart = self.chart_generator.create_kpi_dashboard(summary_data)
            kpi_image = Image(io.BytesIO(kpi_chart), width=6 * inch, height=5.5 * inch)
            elements.append(kpi_image)
            elements.append(Spacer(1, 20))

        # Summary text
        conversation_count = summary_data.get("conversation_count", 0)
        average_minutes = summary_data.get("average_minutes", 0)
        satisfaction = summary_data.get("avg_satisfaction", 0) * 100

        summary_text = f"""
        Durante el período analizado, se registraron <b>{conversation_count:,}</b> llamadas con una 
        duración promedio de <b>{average_minutes:.1f} minutos</b>. La satisfacción del cliente 
        alcanzó un <b>{satisfaction:.1f}%</b>, lo que refleja la calidad del servicio brindado.
        """

        elements.append(Paragraph(summary_text, styles["NormalEnhanced"]))

        return elements

    def _create_detailed_metrics(
        self,
        summary_data: Dict[str, Any],
        topics_data: List[Dict[str, Any]],
        emotions_data: Dict[str, float],
        ratings_data: List[Dict[str, Any]],
        styles,
    ) -> List:
        """Create detailed metrics section with charts"""
        elements = []

        # Topics section
        elements.append(Paragraph(SpanishTexts.MAIN_TOPICS, styles["Heading1Enhanced"]))

        if self.config.include_charts and topics_data:
            topics_chart = self.chart_generator.create_topics_bar_chart(topics_data)
            topics_image = Image(
                io.BytesIO(topics_chart), width=6 * inch, height=3.5 * inch
            )
            elements.append(topics_image)
            elements.append(Spacer(1, 20))

        # Topics table (top 5)
        if topics_data:
            topics_table_data = [[SpanishTexts.TOPIC, SpanishTexts.FREQUENCY]]
            for topic in topics_data[:5]:
                topics_table_data.append(
                    [topic.get("topic", "N/A"), str(topic.get("amount", 0))]
                )

            topics_table = Table(topics_table_data, colWidths=[4 * inch, 1.5 * inch])
            topics_table.setStyle(self._get_enhanced_table_style())
            elements.append(topics_table)

        elements.append(Spacer(1, 30))

        # Sentiment analysis section
        if self.config.include_charts:
            elements.append(PageBreak())
            elements.append(
                Paragraph(SpanishTexts.SENTIMENT_ANALYSIS, styles["Heading1Enhanced"])
            )
            sentiment_chart = self.chart_generator.create_sentiment_donut_chart(
                emotions_data
            )
            sentiment_image = Image(
                io.BytesIO(sentiment_chart), width=5 * inch, height=5 * inch
            )
            elements.append(sentiment_image)
            elements.append(Spacer(1, 20))

        # Ratings section
        if ratings_data:
            elements.append(PageBreak())
            elements.append(
                Paragraph(SpanishTexts.RATING_DISTRIBUTION, styles["Heading1Enhanced"])
            )

            if self.config.include_charts:
                ratings_chart = self.chart_generator.create_ratings_distribution_chart(
                    ratings_data
                )
                ratings_image = Image(
                    io.BytesIO(ratings_chart), width=5 * inch, height=6 * inch
                )
                elements.append(ratings_image)
                elements.append(Spacer(1, 20))

        return elements

    def _create_insights_section(
        self,
        summary_data: Dict[str, Any],
        topics_data: List[Dict[str, Any]],
        emotions_data: Dict[str, float],
        ratings_data: List[Dict[str, Any]],
        styles,
    ) -> List:
        """Create insights and recommendations section"""
        elements = []

        # Key insights
        elements.append(Paragraph(SpanishTexts.INSIGHTS, styles["Heading1Enhanced"]))

        insights = InsightsGenerator.generate_insights(
            summary_data, topics_data, emotions_data, ratings_data
        )

        for i, insight in enumerate(insights, 1):
            elements.append(Paragraph(f"• {insight}", styles["InsightStyle"]))

        elements.append(Spacer(1, 30))

        # Recommendations
        if self.config.include_recommendations:
            elements.append(
                Paragraph(SpanishTexts.RECOMMENDATIONS, styles["Heading1Enhanced"])
            )

            recommendations = InsightsGenerator.generate_recommendations(
                summary_data, emotions_data, ratings_data
            )

            for i, recommendation in enumerate(recommendations, 1):
                elements.append(
                    Paragraph(f"{i}. {recommendation}", styles["InsightStyle"])
                )

        return elements

    def _get_enhanced_table_style(self) -> TableStyle:
        """Get enhanced table styling"""
        return TableStyle(
            [
                # Header styling
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E86AB")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 12),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 15),
                ("TOPPADDING", (0, 0), (-1, 0), 15),
                # Data rows styling
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("ALIGN", (0, 1), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 10),
                # Alternating row colors
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#F8F9FA")],
                ),
                # Grid
                ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#E0E0E0")),
                ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor("#2E86AB")),
            ]
        )


def create_monthly_report(
    company_name: str,
    start_date: datetime,
    end_date: datetime,
    summary_data: Dict[str, Any],
    topics_data: List[Dict[str, Any]],
    categories_data: List[Dict[str, Any]] = None,
    ratings_data: List[Dict[str, Any]] = None,
    emotions_data: Dict[str, float] = None,
    config: ReportConfig = None,
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
    if emotions_data is None:
        emotions_data = {"positive": 0.0, "neutral": 0.0, "negative": 0.0}
    if ratings_data is None:
        ratings_data = []
    if topics_data is None:
        topics_data = []

    generator = ReportGenerator(config)

    return generator.create_monthly_report(
        company_name=company_name,
        start_date=start_date,
        end_date=end_date,
        summary_data=summary_data,
        topics_data=topics_data,
        categories_data=categories_data,
        ratings_data=ratings_data,
        emotions_data=emotions_data,
    )


async def save_report_to_storage(
    supabase,
    pdf_data: bytes,
    company_name: str,
    start_date: datetime,
    user_id: str,
    replace_existing: Optional[bool] = False,
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
    if not pdf_data:
        raise ValueError("PDF data cannot be empty")

    if not user_id:
        raise ValueError("User ID is required")

    report_id = str(uuid.uuid4())
    formatted_date = start_date.strftime("%Y-%m")

    folder_name = create_folder_name(company_name, start_date)
    storage_path = f"{folder_name}/{report_id}.pdf"
    report_table_name = f"Reporte Mensual - {company_name} - {formatted_date}"

    report_exists = False
    continue_operation = True

    if not continue_operation:
        # Return existing report info
        existing_report = (
            supabase.table("reports")
            .select("*")
            .eq("name", report_table_name)
            .single()
            .execute()
        )
        if existing_report.data:
            return {
                "report_id": existing_report.data["report_id"],
                "report_name": existing_report.data["name"],
                "file_url": existing_report.data["file_path"],
                "created_at": existing_report.data["created_at"],
                "details": {"already_existed": True},
            }
        return None

    if report_exists:
        # Cleanup bucket files
        try:
            existing_bucket = supabase.storage.from_("reports").list(folder_name)

            file_array = [
                f"{folder_name}/{bucket_file['name']}"
                for bucket_file in existing_bucket
            ]
            supabase.storage.from_("reports").remove(file_array)
        except Exception:
            raise Exception(f"Failed to delete existing report file in {storage_path}")
        # Cleanup database entries
        try:
            _ = (
                supabase.table("reports")
                .delete()
                .eq("name", report_table_name)
                .execute()
            )
        except Exception:
            raise Exception(
                f"Failed to delete existing report entry: {report_table_name}"
            )
        print(
            f"Successfully deleted all reports and references in {folder_name}. Proceeding with upload..."
        )

    # Upload to Supabase storage
    try:
        max_retries = 3
        for attempt in range(max_retries):
            try:
                supabase.storage.from_("reports").upload(
                    storage_path,
                    pdf_data,
                    file_options={
                        "content-type": "application/pdf",
                        "cache_control": "3600",
                        "upsert": False,
                    },
                )
                break
            except Exception as upload_error:
                if attempt == max_retries - 1:
                    raise Exception(
                        f"Failed to upload report to storage: {str(upload_error)}"
                    )
                continue

        # Get the public URL
        file_url = supabase.storage.from_("reports").get_public_url(storage_path)

        # Create a record in the reports table
        report_data = {
            "report_id": report_id,
            "name": report_table_name,
            "created_by": user_id,
            "type": "pdf",
            "file_path": file_url,
        }

        try:
            db_response = supabase.table("reports").insert(report_data).execute()

            if not db_response.data:
                try:  # if insert fails here we gotta remove from storage
                    supabase.storage.from_("reports").remove([storage_path])
                except Exception:
                    pass
                raise Exception("Failed to insert record into database")
        except Exception as db_error:
            try:  # try to remove it here too
                supabase.storage.from_("reports").remove([storage_path])
            except Exception:
                pass
            raise Exception(f"Database insertion failed: {str(db_error)}")

        return {
            "report_id": report_id,
            "report_name": report_data["name"],
            "file_url": file_url,
            "created_at": datetime.now().isoformat(),
            "details": {"already_existed": report_exists},
        }

    except Exception as e:
        error_msg = (
            f"Report generation failed for {company_name} ({formatted_date}): {str(e)}"
        )
        raise Exception(error_msg)


def create_folder_name(company_name: str, start_date: datetime) -> str:
    formatted_date = start_date.strftime("%Y-%m")
    safe_company_name = "".join(
        c for c in company_name if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()
    safe_company_name = safe_company_name.lower().replace(" ", "_")

    return f"{safe_company_name}_{formatted_date}"
