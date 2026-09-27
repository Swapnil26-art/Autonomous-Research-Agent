"""Export functionality for research summaries."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from src.models import ResearchSummary, ExportFormat, ExportRequest
from src.config import get_settings


class BaseExporter:
    """Abstract base class for exporters."""

    def __init__(self):
        self.settings = get_settings().export
        self.output_dir = Path(self.settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export summary and return output path."""
        raise NotImplementedError

    def _get_output_path(self, summary: ResearchSummary, request: ExportRequest, extension: str) -> Path:
        """Generate output file path."""
        if request.output_path:
            return Path(request.output_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_query = "".join(c for c in summary.query[:50] if c.isalnum() or c in " -_").strip()
        filename = f"{safe_query}_{timestamp}.{extension}"
        return self.output_dir / filename


class MarkdownExporter(BaseExporter):
    """Export summary as Markdown."""

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export to Markdown format."""
        output_path = self._get_output_path(summary, request, "md")

        lines = [
            f"# Research Summary: {summary.query}",
            "",
            f"**Generated:** {summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Processing Time:** {summary.processing_time:.2f}s",
            f"**Sources Analyzed:** {summary.total_sources}",
            "",
            "---",
            ""
        ]

        # Key Points
        if summary.key_points:
            lines.append("## Key Points")
            lines.append("")
            for point in summary.key_points:
                lines.append(f"- {point}")
            lines.append("")

        # Important Findings
        if summary.important_findings:
            lines.append("## Important Findings")
            lines.append("")
            for finding in summary.important_findings:
                lines.append(f"- {finding}")
            lines.append("")

        # Actionable Insights
        if summary.actionable_insights:
            lines.append("## Actionable Insights")
            lines.append("")
            for insight in summary.actionable_insights:
                lines.append(f"- {insight}")
            lines.append("")

        # Detailed Sections
        if summary.sections:
            lines.append("## Detailed Analysis")
            lines.append("")
            for section in summary.sections:
                lines.append(f"### {section.title}")
                lines.append("")
                lines.append(section.content)
                lines.append("")
                if section.sources:
                    lines.append("*Sources:*")
                    for src in section.sources:
                        lines.append(f"- {src}")
                    lines.append("")

        # References
        if summary.references:
            lines.append("## References")
            lines.append("")
            for i, ref in enumerate(summary.references, 1):
                lines.append(f"{i}. **{ref.title}** - {ref.url}")
                if ref.snippet:
                    lines.append(f"   *{ref.snippet}*")
                lines.append("")

        # Metadata
        if request.include_metadata:
            lines.append("---")
            lines.append("")
            lines.append("## Metadata")
            lines.append("")
            lines.append(f"- **Summary ID:** {summary.id}")
            lines.append(f"- **Query:** {summary.query}")
            lines.append(f"- **Generated At:** {summary.generated_at.isoformat()}")
            lines.append(f"- **Total Sources:** {summary.total_sources}")
            lines.append(f"- **Processing Time:** {summary.processing_time:.2f}s")

        content = "\n".join(lines)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Markdown exported to: {output_path}")
        return str(output_path)


class JSONExporter(BaseExporter):
    """Export summary as JSON."""

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export to JSON format."""
        output_path = self._get_output_path(summary, request, "json")

        data = {
            "id": summary.id,
            "query": summary.query,
            "generated_at": summary.generated_at.isoformat(),
            "processing_time": summary.processing_time,
            "total_sources": summary.total_sources,
            "key_points": summary.key_points,
            "important_findings": summary.important_findings,
            "actionable_insights": summary.actionable_insights,
            "sections": [
                {
                    "title": s.title,
                    "content": s.content,
                    "sources": s.sources
                }
                for s in summary.sections
            ],
            "references": [
                {
                    "title": r.title,
                    "url": str(r.url),
                    "snippet": r.snippet,
                    "source": r.source.value,
                    "relevance_score": r.relevance_score
                }
                for r in summary.references
            ]
        }

        if request.include_metadata:
            data["metadata"] = {
                "summary_id": summary.id,
                "query": summary.query,
                "generated_at": summary.generated_at.isoformat()
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON exported to: {output_path}")
        return str(output_path)


class PDFExporter(BaseExporter):
    """Export summary as PDF using reportlab."""

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export to PDF format."""
        output_path = self._get_output_path(summary, request, "pdf")

        try:
            from reportlab.lib.pagesizes import A4, letter
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch, cm
            from reportlab.lib.colors import HexColor
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                Table, TableStyle, ListFlowable, ListItem
            )
            from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
        except ImportError:
            logger.error("reportlab not installed, cannot export PDF")
            # Fallback to markdown
            md_exporter = MarkdownExporter()
            md_path = md_exporter.export(summary, ExportRequest(
                summary_id=summary.id,
                format=ExportFormat.MARKDOWN,
                output_path=str(output_path.with_suffix(".md")),
                include_metadata=request.include_metadata
            ))
            return md_path

        # Page setup
        page_size = A4 if self.settings.pdf_page_size == "A4" else letter
        margin = self._parse_margin(self.settings.pdf_margin)

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=page_size,
            leftMargin=margin,
            rightMargin=margin,
            topMargin=margin,
            bottomMargin=margin
        )

        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            'CustomTitle',
            parent=styles['Title'],
            fontSize=18,
            spaceAfter=12,
            textColor=HexColor('#1a1a2e')
        ))
        styles.add(ParagraphStyle(
            'CustomHeading1',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=16,
            textColor=HexColor('#16213e')
        ))
        styles.add(ParagraphStyle(
            'CustomHeading2',
            parent=styles['Heading2'],
            fontSize=12,
            spaceAfter=6,
            spaceBefore=12,
            textColor=HexColor('#0f3460')
        ))
        styles.add(ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=self.settings.pdf_font_size,
            leading=self.settings.pdf_font_size * 1.4,
            alignment=TA_JUSTIFY,
            spaceAfter=6
        ))
        styles.add(ParagraphStyle(
            'CustomBullet',
            parent=styles['Normal'],
            fontSize=self.settings.pdf_font_size,
            leading=self.settings.pdf_font_size * 1.4,
            leftIndent=20,
            bulletIndent=8,
            spaceAfter=4
        ))
        styles.add(ParagraphStyle(
            'ReferenceStyle',
            parent=styles['Normal'],
            fontSize=self.settings.pdf_font_size - 1,
            leading=(self.settings.pdf_font_size - 1) * 1.3,
            leftIndent=20,
            spaceAfter=4,
            textColor=HexColor('#444')
        ))

        story = []

        # Title
        story.append(Paragraph(f"Research Summary: {summary.query}", styles['CustomTitle']))
        story.append(Spacer(1, 6))

        # Meta info
        meta_style = ParagraphStyle('Meta', parent=styles['Normal'], fontSize=9, textColor=HexColor('#666'))
        story.append(Paragraph(f"Generated: {summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}", meta_style))
        story.append(Paragraph(f"Sources Analyzed: {summary.total_sources} | Processing Time: {summary.processing_time:.2f}s", meta_style))
        story.append(Spacer(1, 12))

        # Horizontal line
        story.append(Paragraph("<hr/>", styles['Normal']))
        story.append(Spacer(1, 12))

        # Key Points
        if summary.key_points:
            story.append(Paragraph("Key Points", styles['CustomHeading1']))
            for point in summary.key_points:
                story.append(Paragraph(f"• {point}", styles['CustomBullet']))
            story.append(Spacer(1, 8))

        # Important Findings
        if summary.important_findings:
            story.append(Paragraph("Important Findings", styles['CustomHeading1']))
            for finding in summary.important_findings:
                story.append(Paragraph(f"• {finding}", styles['CustomBullet']))
            story.append(Spacer(1, 8))

        # Actionable Insights
        if summary.actionable_insights:
            story.append(Paragraph("Actionable Insights", styles['CustomHeading1']))
            for insight in summary.actionable_insights:
                story.append(Paragraph(f"• {insight}", styles['CustomBullet']))
            story.append(Spacer(1, 8))

        # Detailed Sections
        if summary.sections:
            story.append(Paragraph("Detailed Analysis", styles['CustomHeading1']))
            story.append(Spacer(1, 8))
            for section in summary.sections:
                story.append(Paragraph(section.title, styles['CustomHeading2']))
                story.append(Paragraph(section.content, styles['CustomBody']))
                if section.sources:
                    story.append(Paragraph("<b>Sources:</b>", styles['CustomBody']))
                    for src in section.sources:
                        story.append(Paragraph(f"• {src}", styles['ReferenceStyle']))
                story.append(Spacer(1, 8))

        # References
        if summary.references:
            story.append(Paragraph("References", styles['CustomHeading1']))
            story.append(Spacer(1, 8))
            for i, ref in enumerate(summary.references, 1):
                ref_text = f"{i}. <b>{ref.title}</b> - <link href='{ref.url}'>{ref.url}</link>"
                if ref.snippet:
                    ref_text += f"<br/>&nbsp;&nbsp;&nbsp;<i>{ref.snippet}</i>"
                story.append(Paragraph(ref_text, styles['ReferenceStyle']))

        # Metadata
        if request.include_metadata:
            story.append(PageBreak())
            story.append(Paragraph("Metadata", styles['CustomHeading1']))
            meta_data = [
                ["Summary ID", summary.id],
                ["Query", summary.query],
                ["Generated At", summary.generated_at.isoformat()],
                ["Total Sources", str(summary.total_sources)],
                ["Processing Time", f"{summary.processing_time:.2f}s"]
            ]
            table = Table(meta_data, colWidths=[2*inch, 4*inch])
            table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#ddd')),
            ]))
            story.append(table)

        doc.build(story)
        logger.info(f"PDF exported to: {output_path}")
        return str(output_path)

    def _parse_margin(self, margin_str: str) -> float:
        """Parse margin string to points."""
        if margin_str.endswith("cm"):
            return float(margin_str[:-2]) * cm
        elif margin_str.endswith("in"):
            return float(margin_str[:-2]) * inch
        elif margin_str.endswith("mm"):
            return float(margin_str[:-2]) * mm
        return 2 * cm


class HTMLExporter(BaseExporter):
    """Export summary as HTML."""

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export to HTML format."""
        output_path = self._get_output_path(summary, request, "html")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Research Summary: {summary.query}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; max-width: 900px; margin: 0 auto; padding: 2rem; color: #1a1a2e; }}
        h1 {{ color: #1a1a2e; border-bottom: 2px solid #e94560; padding-bottom: 0.5rem; }}
        h2 {{ color: #16213e; margin-top: 2rem; }}
        h3 {{ color: #0f3460; }}
        .meta {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
        .section {{ margin-bottom: 2rem; }}
        .references {{ font-size: 0.9rem; color: #444; }}
        .references a {{ color: #e94560; text-decoration: none; }}
        .references a:hover {{ text-decoration: underline; }}
        ul {{ padding-left: 1.5rem; }}
        li {{ margin-bottom: 0.5rem; }}
        hr {{ border: none; border-top: 1px solid #ddd; margin: 2rem 0; }}
        .source-ref {{ font-size: 0.85rem; color: #666; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Research Summary: {summary.query}</h1>
    <div class="meta">
        Generated: {summary.generated_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
        Sources Analyzed: {summary.total_sources} | Processing Time: {summary.processing_time:.2f}s
    </div>
    <hr>
"""

        if summary.key_points:
            html += "<div class='section'><h2>Key Points</h2><ul>"
            for point in summary.key_points:
                html += f"<li>{point}</li>"
            html += "</ul></div>"

        if summary.important_findings:
            html += "<div class='section'><h2>Important Findings</h2><ul>"
            for finding in summary.important_findings:
                html += f"<li>{finding}</li>"
            html += "</ul></div>"

        if summary.actionable_insights:
            html += "<div class='section'><h2>Actionable Insights</h2><ul>"
            for insight in summary.actionable_insights:
                html += f"<li>{insight}</li>"
            html += "</ul></div>"

        if summary.sections:
            html += "<div class='section'><h2>Detailed Analysis</h2>"
            for section in summary.sections:
                html += f"<h3>{section.title}</h3><p>{section.content}</p>"
                if section.sources:
                    html += "<p class='source-ref'>Sources: " + ", ".join(section.sources) + "</p>"
            html += "</div>"

        if summary.references:
            html += "<div class='section references'><h2>References</h2><ol>"
            for ref in summary.references:
                html += f"<li><b>{ref.title}</b> - <a href='{ref.url}' target='_blank'>{ref.url}</a>"
                if ref.snippet:
                    html += f"<br><i>{ref.snippet}</i>"
                html += "</li>"
            html += "</ol></div>"

        if request.include_metadata:
            html += f"""
    <hr>
    <div class='section'>
        <h2>Metadata</h2>
        <ul>
            <li><b>Summary ID:</b> {summary.id}</li>
            <li><b>Query:</b> {summary.query}</li>
            <li><b>Generated At:</b> {summary.generated_at.isoformat()}</li>
            <li><b>Total Sources:</b> {summary.total_sources}</li>
            <li><b>Processing Time:</b> {summary.processing_time:.2f}s</li>
        </ul>
    </div>
"""

        html += """
</body>
</html>"""

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"HTML exported to: {output_path}")
        return str(output_path)


class ExportManager:
    """Manages export operations."""

    def __init__(self):
        self.exporters = {
            ExportFormat.MARKDOWN: MarkdownExporter(),
            ExportFormat.JSON: JSONExporter(),
            ExportFormat.PDF: PDFExporter(),
            ExportFormat.HTML: HTMLExporter(),
        }

    def export(self, summary: ResearchSummary, request: ExportRequest) -> str:
        """Export summary using appropriate exporter."""
        exporter = self.exporters.get(request.format)
        if not exporter:
            raise ValueError(f"Unsupported export format: {request.format}")

        return exporter.export(summary, request)

    def export_multiple(
        self,
        summary: ResearchSummary,
        formats: list[ExportFormat],
        include_metadata: bool = True
    ) -> dict[ExportFormat, str]:
        """Export to multiple formats."""
        results = {}
        for fmt in formats:
            request = ExportRequest(
                summary_id=summary.id,
                format=fmt,
                include_metadata=include_metadata
            )
            try:
                path = self.export(summary, request)
                results[fmt] = path
            except Exception as e:
                logger.error(f"Export to {fmt} failed: {e}")
                results[fmt] = f"Error: {e}"
        return results