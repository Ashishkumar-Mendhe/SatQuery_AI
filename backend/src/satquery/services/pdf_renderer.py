"""High-fidelity PDF document rendering service using ReportLab."""

from __future__ import annotations

import html
import io
import logging
from datetime import UTC, datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from satquery.api.schemas.reports import ReportSnapshot
from satquery.services.asset_store import AssetStore

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):  # type: ignore[misc]
    """Two-pass canvas to dynamically compute and stamp total page count (Page X of Y)."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))

        # Top Running Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(15 * mm, 287 * mm, "SatQuery AI — Geospatial Analysis Dossier")
            self.drawRightString(
                195 * mm, 287 * mm, datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
            )
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(15 * mm, 284 * mm, 195 * mm, 284 * mm)

        # Bottom Running Footer (all pages)
        self.setStrokeColor(colors.HexColor("#cbd5e1"))
        self.setLineWidth(0.5)
        self.line(15 * mm, 12 * mm, 195 * mm, 12 * mm)

        self.drawString(15 * mm, 8 * mm, "SatQuery AI | Confidential & Grounded Geospatial Dossier")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(195 * mm, 8 * mm, page_str)

        self.restoreState()


class SatQueryPdfRenderer:
    """Renders professional, traceable A4 PDF dossiers from ReportSnapshot models."""

    def __init__(self, asset_store: AssetStore | None = None) -> None:
        self.asset_store = asset_store

    def render_pdf(self, snapshot: ReportSnapshot) -> bytes:
        """Render snapshot into standard A4 PDF byte stream."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title=snapshot.title,
            author="SatQuery AI Evidence Engine",
        )

        styles = self._build_styles()
        story: list[Any] = []

        # 1. Header Banner & Identity
        story.extend(self._build_header(snapshot, styles))
        story.append(Spacer(1, 4 * mm))

        # 2. Executive Summary & Context
        story.extend(self._build_executive_summary(snapshot, styles))
        story.append(Spacer(1, 4 * mm))

        # 3. Source Imagery & Sensors
        if snapshot.scenes:
            story.extend(self._build_scenes_section(snapshot, styles))
            story.append(Spacer(1, 4 * mm))

        # 4. Quantitative Findings & Change Metrics
        story.extend(self._build_quantitative_section(snapshot, styles))
        story.append(Spacer(1, 4 * mm))

        # 5. Visual Evidence & Figures
        if snapshot.figures:
            story.extend(self._build_figures_section(snapshot, styles))
            story.append(Spacer(1, 4 * mm))

        # 6. AI Interpretation & Visual Predictions
        story.extend(self._build_interpretation_section(snapshot, styles))
        story.append(Spacer(1, 4 * mm))

        # 7. Confidence, Quality Factors & Limitations
        story.extend(self._build_confidence_section(snapshot, styles))
        story.append(Spacer(1, 4 * mm))

        # 8. Provenance & Methods Register
        story.extend(self._build_provenance_section(snapshot, styles))

        doc.build(story, canvasmaker=NumberedCanvas)
        return buffer.getvalue()

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        """Construct typography and color palette styles for the PDF."""
        base = getSampleStyleSheet()

        styles: dict[str, ParagraphStyle] = {
            "Title": ParagraphStyle(
                "CustomTitle",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=18,
                leading=22,
                textColor=colors.HexColor("#0f172a"),
            ),
            "Subtitle": ParagraphStyle(
                "CustomSubtitle",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#475569"),
            ),
            "SectionH2": ParagraphStyle(
                "CustomH2",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=12,
                leading=16,
                textColor=colors.HexColor("#0f172a"),
                spaceBefore=8,
                spaceAfter=4,
            ),
            "SectionH3": ParagraphStyle(
                "CustomH3",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=10,
                leading=13,
                textColor=colors.HexColor("#1e293b"),
                spaceBefore=4,
                spaceAfter=2,
            ),
            "Body": ParagraphStyle(
                "CustomBody",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#334155"),
            ),
            "BodyBold": ParagraphStyle(
                "CustomBodyBold",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=9,
                leading=13,
                textColor=colors.HexColor("#0f172a"),
            ),
            "Small": ParagraphStyle(
                "CustomSmall",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=7.5,
                leading=10.5,
                textColor=colors.HexColor("#64748b"),
            ),
            "Code": ParagraphStyle(
                "CustomCode",
                parent=base["Normal"],
                fontName="Courier",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#0f172a"),
            ),
            "BadgeMock": ParagraphStyle(
                "BadgeMock",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#b45309"),
            ),
            "BadgeReal": ParagraphStyle(
                "BadgeReal",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#047857"),
            ),
            "TableHeader": ParagraphStyle(
                "TableHeader",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8.5,
                leading=11,
                textColor=colors.HexColor("#0f172a"),
            ),
            "TableCell": ParagraphStyle(
                "TableCell",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#334155"),
            ),
            "TableCellBold": ParagraphStyle(
                "TableCellBold",
                parent=base["Normal"],
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor("#0f172a"),
            ),
            "Callout": ParagraphStyle(
                "CustomCallout",
                parent=base["Normal"],
                fontName="Helvetica",
                fontSize=8.5,
                leading=12,
                textColor=colors.HexColor("#1e293b"),
            ),
        }
        return styles

    def _build_header(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []

        # Top Bar with Origin Badge
        if snapshot.is_mock_data:
            badge_text = "<b>[ SYNTHETIC DEMO DATA — NOT A MEASURED SATELLITE OBSERVATION ]</b>"
            badge_p = Paragraph(badge_text, styles["BadgeMock"])
            badge_table = Table(
                [[badge_p]],
                colWidths=[180 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f59e0b")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                ),
            )
            items.append(badge_table)
            items.append(Spacer(1, 2 * mm))
        elif snapshot.is_fallback_data:
            badge_text = "<b>[ FALLBACK SYNTHETIC DATA — PRIMARY SATELLITE UNAVAILABLE ]</b>"
            badge_p = Paragraph(badge_text, styles["BadgeMock"])
            badge_table = Table(
                [[badge_p]],
                colWidths=[180 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffedd5")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f97316")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]
                ),
            )
            items.append(badge_table)
            items.append(Spacer(1, 2 * mm))

        # Title and Subtitle
        title_esc = html.escape(snapshot.title)
        items.append(Paragraph(title_esc, styles["Title"]))
        sub_text = (
            f"Report ID: <b>{snapshot.report_id}</b> | "
            f"Analysis Timestamp: <b>{snapshot.analysis_timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</b> | "
            f"Origin: <b>{snapshot.data_origin.value.upper()}</b>"
        )
        items.append(Paragraph(sub_text, styles["Subtitle"]))
        items.append(Spacer(1, 2 * mm))
        items.append(
            HRFlowable(
                width="100%",
                thickness=1,
                color=colors.HexColor("#0f172a"),
                spaceBefore=2,
                spaceAfter=4,
            )
        )
        return items

    def _build_executive_summary(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(Paragraph("1. Executive Summary & Context", styles["SectionH2"]))

        # Query & AOI Info Table
        query_text = html.escape(snapshot.query or "General Multi-Temporal Land Surface Analysis")
        aoi_coords = (
            f"[{snapshot.aoi.bbox[0]:.4f}, {snapshot.aoi.bbox[1]:.4f}, {snapshot.aoi.bbox[2]:.4f}, {snapshot.aoi.bbox[3]:.4f}]"
            if snapshot.aoi.bbox
            else "N/A"
        )
        aoi_area = float(snapshot.aoi.area_km2 or 0.0)

        context_data = [
            [
                Paragraph("<b>Analysis Query:</b>", styles["TableCellBold"]),
                Paragraph(query_text, styles["TableCell"]),
            ],
            [
                Paragraph("<b>AOI Extent:</b>", styles["TableCellBold"]),
                Paragraph(f"{aoi_coords} (WGS84 EPSG:4326)", styles["TableCell"]),
            ],
            [
                Paragraph("<b>AOI Total Area:</b>", styles["TableCellBold"]),
                Paragraph(
                    f"<b>{aoi_area:.4f} km²</b> ({aoi_area * 100:.2f} ha)",
                    styles["TableCell"],
                ),
            ],
        ]
        if snapshot.date_range:
            context_data.append(
                [
                    Paragraph("<b>Requested Window:</b>", styles["TableCellBold"]),
                    Paragraph(
                        f"{snapshot.date_range.start_date} to {snapshot.date_range.end_date}",
                        styles["TableCell"],
                    ),
                ]
            )

        ctx_table = Table(
            context_data,
            colWidths=[40 * mm, 140 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            ),
        )
        items.append(ctx_table)
        items.append(Spacer(1, 2 * mm))

        # Main Answer Narrative
        if snapshot.answer:
            ans_clean = html.escape(snapshot.answer).replace("\n", "<br/>")
            ans_box = Table(
                [[Paragraph(f"<b>Grounded Synthesis:</b><br/>{ans_clean}", styles["Callout"])]],
                colWidths=[180 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f5f9")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                ),
            )
            items.append(ans_box)

        return items

    def _build_scenes_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(Paragraph("2. Source Satellite Imagery Assets", styles["SectionH2"]))

        headers = ["Scene ID", "Platform", "Acquisition UTC", "Cloud %", "Resolution"]
        table_rows: list[list[Any]] = [
            [Paragraph(f"<b>{h}</b>", styles["TableHeader"]) for h in headers]
        ]

        for sc in snapshot.scenes:
            acq_str = sc.acquisition_time.strftime("%Y-%m-%d %H:%M:%S")
            cloud_str = f"{sc.cloud_cover:.1f}%" if sc.cloud_cover is not None else "N/A"
            table_rows.append(
                [
                    Paragraph(html.escape(sc.id), styles["TableCellBold"]),
                    Paragraph(
                        html.escape(sc.platform or sc.sensor_type.value), styles["TableCell"]
                    ),
                    Paragraph(acq_str, styles["TableCell"]),
                    Paragraph(cloud_str, styles["TableCell"]),
                    Paragraph(
                        f"{sc.resolution_meters:.1f} m" if sc.resolution_meters else "10.0 m",
                        styles["TableCell"],
                    ),
                ]
            )

        scenes_table = Table(
            table_rows,
            colWidths=[65 * mm, 30 * mm, 42 * mm, 20 * mm, 23 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                ]
            ),
        )
        items.append(scenes_table)
        return items

    def _build_quantitative_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(
            Paragraph(
                "3. Quantitative Surface Measurements & Change Analytics", styles["SectionH2"]
            )
        )

        summary = snapshot.quantitative_summary
        aoi_area = float(snapshot.aoi.area_km2 or 0.0)
        valid_comp_area = summary.get("valid_comparison_area_km2", aoi_area)
        valid_cov_pct = summary.get("valid_comparison_coverage_percent", 100.0)

        # Main Change / Land Surface Table
        headers = [
            "Land Surface Category",
            "Area (km²)",
            "Area (ha)",
            "% of Valid Comparison",
            "Measurement Basis / Denominator",
        ]
        rows: list[list[Any]] = [[Paragraph(f"<b>{h}</b>", styles["TableHeader"]) for h in headers]]

        if snapshot.change_metrics:
            cm = snapshot.change_metrics
            rows.append(
                [
                    Paragraph("<b>Gain / Spectral Increase</b>", styles["TableCellBold"]),
                    Paragraph(f"{cm.gain_area_km2:.4f}", styles["TableCell"]),
                    Paragraph(f"{cm.gain_area_km2 * 100:.2f}", styles["TableCell"]),
                    Paragraph(
                        f"<b>{summary.get('gain_percent_of_valid_comparison', cm.pixel_counts.gain_percent):.2f}%</b>",
                        styles["TableCell"],
                    ),
                    Paragraph(
                        f"V = {valid_comp_area:.2f} km² (shared valid pixels)", styles["Small"]
                    ),
                ]
            )
            rows.append(
                [
                    Paragraph("<b>Loss / Spectral Decrease</b>", styles["TableCellBold"]),
                    Paragraph(f"{cm.loss_area_km2:.4f}", styles["TableCell"]),
                    Paragraph(f"{cm.loss_area_km2 * 100:.2f}", styles["TableCell"]),
                    Paragraph(
                        f"<b>{summary.get('loss_percent_of_valid_comparison', cm.pixel_counts.loss_percent):.2f}%</b>",
                        styles["TableCell"],
                    ),
                    Paragraph(
                        f"V = {valid_comp_area:.2f} km² (shared valid pixels)", styles["Small"]
                    ),
                ]
            )
            rows.append(
                [
                    Paragraph("<b>Stable / Unchanged</b>", styles["TableCellBold"]),
                    Paragraph(f"{cm.stable_area_km2:.4f}", styles["TableCell"]),
                    Paragraph(f"{cm.stable_area_km2 * 100:.2f}", styles["TableCell"]),
                    Paragraph(
                        f"<b>{summary.get('stable_percent_of_valid_comparison', cm.pixel_counts.stable_percent):.2f}%</b>",
                        styles["TableCell"],
                    ),
                    Paragraph(
                        f"V = {valid_comp_area:.2f} km² (shared valid pixels)", styles["Small"]
                    ),
                ]
            )
            if summary.get("uncertain_area_km2", 0.0) > 0:
                rows.append(
                    [
                        Paragraph("Uncertain / Near-Threshold", styles["TableCell"]),
                        Paragraph(f"{summary['uncertain_area_km2']:.4f}", styles["TableCell"]),
                        Paragraph(
                            f"{summary['uncertain_area_km2'] * 100:.2f}", styles["TableCell"]
                        ),
                        Paragraph(
                            f"{summary.get('uncertain_percent_of_valid_comparison', 0.0):.2f}%",
                            styles["TableCell"],
                        ),
                        Paragraph(f"V = {valid_comp_area:.2f} km²", styles["Small"]),
                    ]
                )

            # Excluded Area Row
            excluded_km2 = summary.get("excluded_area_km2", 0.0)
            excluded_pct = summary.get("excluded_percent_of_aoi", 0.0)
            rows.append(
                [
                    Paragraph("<i>Excluded (Outside Valid Domain)</i>", styles["TableCell"]),
                    Paragraph(f"{excluded_km2:.4f}", styles["TableCell"]),
                    Paragraph(f"{excluded_km2 * 100:.2f}", styles["TableCell"]),
                    Paragraph(f"{excluded_pct:.2f}% (of AOI)", styles["TableCell"]),
                    Paragraph(f"A = {aoi_area:.2f} km² (AOI total domain)", styles["Small"]),
                ]
            )

            # Valid Comparison Total Row
            rows.append(
                [
                    Paragraph("<b>Total Valid Comparison Domain</b>", styles["TableCellBold"]),
                    Paragraph(f"<b>{valid_comp_area:.4f}</b>", styles["TableCellBold"]),
                    Paragraph(f"<b>{valid_comp_area * 100:.2f}</b>", styles["TableCellBold"]),
                    Paragraph(f"<b>{valid_cov_pct:.2f}% (Coverage)</b>", styles["TableCellBold"]),
                    Paragraph("Shared mutual coverage across both dates", styles["Small"]),
                ]
            )
        elif snapshot.spectral_metrics:
            for sm in snapshot.spectral_metrics:
                mean_val = f"{sm.mean:.4f}" if sm.mean is not None else "N/A"
                min_val = f"{sm.minimum:.4f}" if sm.minimum is not None else "N/A"
                max_val = f"{sm.maximum:.4f}" if sm.maximum is not None else "N/A"
                rows.append(
                    [
                        Paragraph(f"<b>{sm.index_name} Index</b>", styles["TableCellBold"]),
                        Paragraph(mean_val, styles["TableCell"]),
                        Paragraph(f"[{min_val}, {max_val}]", styles["TableCell"]),
                        Paragraph("100.0%", styles["TableCell"]),
                        Paragraph(f"Calculated on Scene {sm.scene_id[:16]}", styles["Small"]),
                    ]
                )

        metrics_table = Table(
            rows,
            colWidths=[48 * mm, 22 * mm, 22 * mm, 38 * mm, 50 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -2),
                        [colors.white, colors.HexColor("#f8fafc")],
                    ),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f1f5f9")),
                ]
            ),
        )
        items.append(metrics_table)

        # Denominator Footnote
        if summary.get("denominator_explanation"):
            items.append(Spacer(1, 1.5 * mm))
            items.append(
                Paragraph(
                    f"<i><b>Measurement Notice:</b> {summary['denominator_explanation']}</i>",
                    styles["Small"],
                )
            )

        return items

    def _build_figures_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(
            Paragraph("4. Visual Evidence & Registered Geospatial Figures", styles["SectionH2"])
        )

        for fig in snapshot.figures:
            fig_items: list[Any] = []
            fig_title = f"<b>{html.escape(fig.title)}</b>"
            fig_items.append(Paragraph(fig_title, styles["SectionH3"]))

            # Attempt to embed raster preview image if asset exists
            image_embedded = False
            if fig.asset_id and self.asset_store:
                try:
                    record = self.asset_store.get_asset(fig.asset_id)
                    if record and record.file_path.exists():
                        img_path = str(record.file_path)
                        img = Image(img_path, width=160 * mm, height=90 * mm)
                        fig_items.append(img)
                        image_embedded = True
                except Exception as e:
                    logger.warning(f"Could not load figure asset {fig.asset_id}: {e}")

            if not image_embedded:
                # Render structured vector placeholder box
                placeholder_data = [
                    [
                        Paragraph(
                            f"<b>Registered Evidence Asset:</b> {fig.figure_id}<br/>"
                            f"<b>Type:</b> {fig.figure_type.value} | <b>Origin:</b> {fig.data_origin.value}<br/>"
                            f"<i>Asset raster linked via ID: {fig.asset_id or 'Vector Geometry Overlay'}</i>",
                            styles["Small"],
                        )
                    ]
                ]
                pbox = Table(
                    placeholder_data,
                    colWidths=[170 * mm],
                    style=TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#cbd5e1")),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ]
                    ),
                )
                fig_items.append(pbox)

            # Caption and legend
            fig_items.append(Spacer(1, 1 * mm))
            fig_items.append(
                Paragraph(f"<i>Figure Caption:</i> {html.escape(fig.caption)}", styles["Small"])
            )

            if fig.legend_items:
                legend_texts = [
                    f"<font color='{leg.get('color', '#000')}'>■</font> {leg.get('label', '')}"
                    for leg in fig.legend_items
                ]
                legend_p = Paragraph(
                    "<b>Legend:</b> " + " &nbsp;&nbsp;|&nbsp;&nbsp; ".join(legend_texts),
                    styles["Small"],
                )
                fig_items.append(legend_p)

            fig_items.append(Spacer(1, 3 * mm))
            items.append(KeepTogether(fig_items))

        return items

    def _build_interpretation_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(
            Paragraph("5. AI Interpretation & Grounded Model Predictions", styles["SectionH2"])
        )

        # Claims
        if snapshot.claims:
            items.append(Paragraph("<b>Verified Grounded Claims:</b>", styles["SectionH3"]))
            for cl in snapshot.claims:
                ev_str = f" [Evidence: {', '.join(cl.evidence_ids)}]" if cl.evidence_ids else ""
                claim_p = Paragraph(
                    f"• <b>[{cl.kind.upper()}]</b> {html.escape(cl.display_text)}<i>{ev_str}</i>",
                    styles["Body"],
                )
                items.append(claim_p)
            items.append(Spacer(1, 2 * mm))

        # Model Predictions (Disclaimed)
        if snapshot.observations:
            items.append(Paragraph("<b>Visual Model Observations (VQA):</b>", styles["SectionH3"]))
            disclaimer = Paragraph(
                "<b>DISCLAIMER:</b> <i>Visual bounding boxes and object tags below represent AI vision model predictions. "
                "They are not verified ground truth and must not be conflated with physical measurements.</i>",
                styles["Small"],
            )
            items.append(disclaimer)
            items.append(Spacer(1, 1.5 * mm))

            obs_rows: list[list[Any]] = [
                [
                    Paragraph("<b>Observation Label</b>", styles["TableHeader"]),
                    Paragraph("<b>Canonical Box [0..1]</b>", styles["TableHeader"]),
                    Paragraph("<b>Map Grounding</b>", styles["TableHeader"]),
                    Paragraph("<b>Verification / Coordinates</b>", styles["TableHeader"]),
                ]
            ]
            for obs in snapshot.observations:
                box_str = (
                    f"[{', '.join(f'{v:.2f}' for v in obs.canonical_box)}]"
                    if obs.canonical_box
                    else "N/A"
                )
                obs_rows.append(
                    [
                        Paragraph(
                            f"<b>{html.escape(obs.label)}</b><br/><font color='#64748b'>{html.escape(obs.description)}</font>",
                            styles["TableCell"],
                        ),
                        Paragraph(box_str, styles["Code"]),
                        Paragraph(obs.map_grounding_status.value, styles["TableCell"]),
                        Paragraph(obs.coordinate_status.value, styles["TableCellBold"]),
                    ]
                )

            obs_table = Table(
                obs_rows,
                colWidths=[65 * mm, 45 * mm, 35 * mm, 35 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#fef3c7")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                ),
            )
            items.append(obs_table)

        return items

    def _build_confidence_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(
            Paragraph("6. Confidence Calibration, Caveats & Limitations", styles["SectionH2"])
        )

        # Confidence breakdown table
        if snapshot.confidence_breakdown:
            cb = snapshot.confidence_breakdown
            overall_pct = round(cb.overall * 100)
            items.append(
                Paragraph(
                    f"<b>Calibrated Confidence Score: {overall_pct}%</b> (Method: {html.escape(cb.methodology)})",
                    styles["BodyBold"],
                )
            )
            items.append(Spacer(1, 1.5 * mm))

            factor_rows: list[list[Any]] = [
                [
                    Paragraph("<b>Confidence Factor</b>", styles["TableHeader"]),
                    Paragraph("<b>Score</b>", styles["TableHeader"]),
                    Paragraph("<b>Weight</b>", styles["TableHeader"]),
                    Paragraph("<b>Evaluation & Quality Details</b>", styles["TableHeader"]),
                ]
            ]
            for factor in cb.factors:
                factor_rows.append(
                    [
                        Paragraph(f"<b>{html.escape(factor.label)}</b>", styles["TableCellBold"]),
                        Paragraph(f"{round(factor.score * 100)}%", styles["TableCell"]),
                        Paragraph(f"{factor.weight:.2f}", styles["TableCell"]),
                        Paragraph(html.escape(factor.explanation), styles["TableCell"]),
                    ]
                )

            factor_table = Table(
                factor_rows,
                colWidths=[40 * mm, 18 * mm, 18 * mm, 104 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                ),
            )
            items.append(factor_table)
            items.append(Spacer(1, 2 * mm))

        # Warnings and Limitations
        if snapshot.warnings or snapshot.limitations:
            caveat_items: list[str] = []
            for w in snapshot.warnings:
                caveat_items.append(
                    f"<b>[{w.severity.value.upper()}] {html.escape(w.title)}:</b> {html.escape(w.message)}"
                )
            for lim in snapshot.limitations:
                caveat_items.append(f"• {html.escape(lim)}")

            warn_p = Paragraph("<br/>".join(caveat_items), styles["Small"])
            warn_box = Table(
                [
                    [
                        Paragraph(
                            "<b>Operational Limitations & Caveats:</b>", styles["TableCellBold"]
                        )
                    ],
                    [warn_p],
                ],
                colWidths=[180 * mm],
                style=TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff1f2")),
                        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#f43f5e")),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                ),
            )
            items.append(warn_box)

        return items

    def _build_provenance_section(
        self, snapshot: ReportSnapshot, styles: dict[str, ParagraphStyle]
    ) -> list[Any]:
        items: list[Any] = []
        items.append(
            Paragraph("7. Provenance, Audit Register & Verification Signature", styles["SectionH2"])
        )

        prov = snapshot.provenance
        checksum_str = snapshot.checksum_sha256 or "COMPUTING"

        prov_rows = [
            [
                Paragraph("<b>Pipeline Version:</b>", styles["TableCellBold"]),
                Paragraph(str(prov.get("pipeline_version", "1.0.0")), styles["TableCell"]),
                Paragraph("<b>Report Schema:</b>", styles["TableCellBold"]),
                Paragraph(str(snapshot.schema_version), styles["TableCell"]),
            ],
            [
                Paragraph("<b>Generated At:</b>", styles["TableCellBold"]),
                Paragraph(
                    snapshot.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"), styles["TableCell"]
                ),
                Paragraph("<b>Snapshot SHA-256:</b>", styles["TableCellBold"]),
                Paragraph(
                    f"<code>{checksum_str[:20]}...{checksum_str[-8:]}</code>", styles["TableCell"]
                ),
            ],
            [
                Paragraph("<b>Source Attribution:</b>", styles["TableCellBold"]),
                Paragraph(
                    "Contains modified Copernicus Sentinel data / Earth Search Element 84",
                    styles["TableCell"],
                ),
                Paragraph("<b>Verification Engine:</b>", styles["TableCellBold"]),
                Paragraph("SatQuery AI Deterministic Auditor", styles["TableCell"]),
            ],
        ]

        prov_table = Table(
            prov_rows,
            colWidths=[35 * mm, 55 * mm, 35 * mm, 55 * mm],
            style=TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            ),
        )
        items.append(prov_table)
        return items
