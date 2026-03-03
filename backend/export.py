"""Markdown and PDF export for coverage reports."""

import os
from datetime import datetime
from fpdf import FPDF

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "exports")


def _sanitize_for_pdf(text: str) -> str:
    """Replace Unicode characters unsupported by Helvetica with ASCII equivalents."""
    replacements = {
        "\u2014": "-",   # em dash
        "\u2013": "-",   # en dash
        "\u2018": "'",   # left single quote
        "\u2019": "'",   # right single quote
        "\u201c": '"',   # left double quote
        "\u201d": '"',   # right double quote
        "\u2026": "...", # ellipsis
        "\u00a0": " ",   # non-breaking space
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Fallback: replace any remaining non-latin1 chars
    return text.encode("latin-1", errors="replace").decode("latin-1")


def ensure_exports_dir():
    """Create exports directory if it doesn't exist."""
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def export_markdown(report: dict, rubric_title: str, submission_title: str) -> str:
    """Export a coverage report as Markdown.

    Args:
        report: Report dict with "items" and "summary" keys.
        rubric_title: Title of the rubric.
        submission_title: Title of the submission.

    Returns:
        Markdown string.
    """
    summary = report["summary"]
    items = report["items"]
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"# RubricLens Coverage Report")
    lines.append("")
    lines.append(f"**Rubric:** {rubric_title}")
    lines.append(f"**Draft:** {submission_title}")
    lines.append(f"**Date:** {date_str}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Criteria:** {summary['total_criteria']}")
    lines.append(f"- **Strong:** {summary['strong']}")
    lines.append(f"- **Partial:** {summary['partial']}")
    lines.append(f"- **Missing:** {summary['missing']}")
    lines.append(f"- **Coverage:** {summary['coverage_pct']}%")
    lines.append("")

    # Top priorities
    if summary["top_priorities"]:
        lines.append("## Top Priorities")
        lines.append("")
        for i, p in enumerate(summary["top_priorities"], 1):
            lines.append(f"{i}. **{p['criterion_name']}** ({p['status']}, {p['max_marks']} marks)")
            lines.append(f"   - {p['next_action']}")
        lines.append("")

    # Overview table
    lines.append("## Criterion Overview")
    lines.append("")
    lines.append("| Criterion | Status | Strength | Max Marks | Next Action |")
    lines.append("|-----------|--------|----------|-----------|-------------|")
    for item in items:
        strength_pct = f"{item['evidence_strength']:.0%}"
        # Truncate next_action for table
        action_short = item["next_action"][:60] + "..." if len(item["next_action"]) > 60 else item["next_action"]
        lines.append(
            f"| {item['criterion_name']} | {item['status']} | {strength_pct} | {item['max_marks']} | {action_short} |"
        )
    lines.append("")

    # Detailed sections
    lines.append("## Detailed Analysis")
    lines.append("")
    for item in items:
        lines.append(f"### {item['criterion_name']}")
        lines.append("")
        lines.append(f"- **Status:** {item['status']}")
        lines.append(f"- **Evidence Strength:** {item['evidence_strength']:.2f}")
        lines.append(f"- **Max Marks:** {item['max_marks']}")
        lines.append("")
        lines.append(f"**Rationale:** {item['rationale']}")
        lines.append("")
        lines.append(f"**Next Action:** {item['next_action']}")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def save_markdown(report: dict, rubric_title: str, submission_title: str, filename: str = None) -> str:
    """Export and save a Markdown report to the exports directory.

    Returns the file path.
    """
    ensure_exports_dir()
    content = export_markdown(report, rubric_title, submission_title)
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


class ReportPDF(FPDF):
    """Custom PDF class for coverage reports."""

    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 10, "RubricLens Coverage Report", new_x="LMARGIN", new_y="NEXT", align="C")
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def status_colour(self, status: str):
        """Set fill colour based on status."""
        if status == "Missing":
            self.set_fill_color(233, 69, 96)  # Red
        elif status == "Partial":
            self.set_fill_color(253, 203, 110)  # Amber
        else:
            self.set_fill_color(0, 184, 148)  # Green
        self.set_text_color(255, 255, 255)

    def reset_colour(self):
        self.set_fill_color(255, 255, 255)
        self.set_text_color(0, 0, 0)


def export_pdf(report: dict, rubric_title: str, submission_title: str) -> bytes:
    """Export a coverage report as PDF bytes.

    Args:
        report: Report dict with "items" and "summary" keys.
        rubric_title: Title of the rubric.
        submission_title: Title of the submission.

    Returns:
        PDF file content as bytes.
    """
    summary = report["summary"]
    items = report["items"]
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Sanitize all text for PDF compatibility
    rubric_title = _sanitize_for_pdf(rubric_title)
    submission_title = _sanitize_for_pdf(submission_title)
    for item in items:
        for key in ("criterion_name", "rationale", "next_action"):
            if key in item:
                item[key] = _sanitize_for_pdf(item[key])
    for p in summary.get("top_priorities", []):
        for key in ("criterion_name", "next_action"):
            if key in p:
                p[key] = _sanitize_for_pdf(p[key])

    pdf = ReportPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Meta info
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Rubric: {rubric_title}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Draft: {submission_title}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Date: {date_str}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Summary section
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total Criteria: {summary['total_criteria']}    |    Strong: {summary['strong']}    |    Partial: {summary['partial']}    |    Missing: {summary['missing']}    |    Coverage: {summary['coverage_pct']}%", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Top priorities
    if summary["top_priorities"]:
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Top Priorities", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for i, p in enumerate(summary["top_priorities"], 1):
            pdf.multi_cell(0, 5, f"{i}. {p['criterion_name']} ({p['status']}, {p['max_marks']} marks): {p['next_action']}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Overview table
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Criterion Overview", new_x="LMARGIN", new_y="NEXT")

    # Table header
    pdf.set_font("Helvetica", "B", 8)
    col_widths = [60, 20, 20, 15, 75]
    headers = ["Criterion", "Status", "Strength", "Marks", "Next Action"]
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 7, header, border=1)
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 8)
    for item in items:
        # Status badge
        pdf.cell(col_widths[0], 7, item["criterion_name"][:35], border=1)
        pdf.status_colour(item["status"])
        pdf.cell(col_widths[1], 7, item["status"], border=1, fill=True, align="C")
        pdf.reset_colour()
        pdf.cell(col_widths[2], 7, f"{item['evidence_strength']:.0%}", border=1, align="C")
        pdf.cell(col_widths[3], 7, str(item["max_marks"]), border=1, align="C")
        action_short = item["next_action"][:45] + "..." if len(item["next_action"]) > 45 else item["next_action"]
        pdf.cell(col_widths[4], 7, action_short, border=1)
        pdf.ln()

    pdf.ln(6)

    # Detailed sections
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Detailed Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    for item in items:
        # Check if we need a new page
        if pdf.get_y() > 240:
            pdf.add_page()

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, item["criterion_name"], new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 9)
        pdf.status_colour(item["status"])
        pdf.cell(25, 6, item["status"], fill=True)
        pdf.reset_colour()
        pdf.cell(0, 6, f"   Strength: {item['evidence_strength']:.2f}   |   Max Marks: {item['max_marks']}", new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 5, f"Rationale: {item['rationale']}", new_x="LMARGIN", new_y="NEXT")
        pdf.multi_cell(0, 5, f"Next Action: {item['next_action']}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    return pdf.output()


def save_pdf(report: dict, rubric_title: str, submission_title: str, filename: str = None) -> str:
    """Export and save a PDF report to the exports directory.

    Returns the file path.
    """
    ensure_exports_dir()
    content = export_pdf(report, rubric_title, submission_title)
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.pdf"
    filepath = os.path.join(EXPORTS_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)
    return filepath
