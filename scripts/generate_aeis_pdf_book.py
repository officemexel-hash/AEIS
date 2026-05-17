from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from PIL import Image as PILImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "docs" / "aeis_full_documentation"
SCREENSHOT_DIR = DOC_DIR / "screenshots"
OUTPUT_DIR = ROOT / "output" / "pdf"
OUTPUT_PDF = OUTPUT_DIR / "AEIS_SYSTEM_BOOK_FULL_2026.pdf"

SOURCE_DOCS = [
    DOC_DIR / "00_INDEX.md",
    DOC_DIR / "01_START_I_ARCHITEKTURA.md",
    DOC_DIR / "02_MODULY_API_UI.md",
    DOC_DIR / "03_PROJEKTY_FAZY_TUTORIAL.md",
    DOC_DIR / "04_KONFIG_ORCHESTRACJA_TESTY.md",
    DOC_DIR / "05_FUNDING_MOBILE_HELPTIPS.md",
]


def register_fonts() -> tuple[str, str, str, str]:
    fonts = Path("C:/Windows/Fonts")
    regular = fonts / "arial.ttf"
    bold = fonts / "arialbd.ttf"
    italic = fonts / "ariali.ttf"
    mono = fonts / "consola.ttf"

    if regular.exists():
        pdfmetrics.registerFont(TTFont("AEIS-Regular", str(regular)))
        pdfmetrics.registerFont(TTFont("AEIS-Bold", str(bold if bold.exists() else regular)))
        pdfmetrics.registerFont(TTFont("AEIS-Italic", str(italic if italic.exists() else regular)))
    else:
        return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"

    if mono.exists():
        pdfmetrics.registerFont(TTFont("AEIS-Mono", str(mono)))
        mono_name = "AEIS-Mono"
    else:
        mono_name = "Courier"
    return "AEIS-Regular", "AEIS-Bold", "AEIS-Italic", mono_name


FONT, FONT_BOLD, FONT_ITALIC, FONT_MONO = register_fonts()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=base["Title"],
            fontName=FONT_BOLD,
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#102033"),
            spaceAfter=18,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName=FONT,
            fontSize=12,
            leading=17,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#405060"),
            spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName=FONT_BOLD,
            fontSize=20,
            leading=25,
            textColor=colors.HexColor("#102033"),
            spaceBefore=10,
            spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName=FONT_BOLD,
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#173f68"),
            spaceBefore=12,
            spaceAfter=7,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base["Heading3"],
            fontName=FONT_BOLD,
            fontSize=12.5,
            leading=16,
            textColor=colors.HexColor("#24465d"),
            spaceBefore=8,
            spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=13,
            alignment=TA_LEFT,
            textColor=colors.HexColor("#1f2933"),
            spaceAfter=5,
        ),
        "small": ParagraphStyle(
            "small",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=7.2,
            leading=9.3,
            textColor=colors.HexColor("#1f2933"),
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["BodyText"],
            fontName=FONT_ITALIC,
            fontSize=7.5,
            leading=9.5,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#475569"),
            spaceBefore=3,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9,
            leading=12.5,
            leftIndent=13,
            bulletIndent=4,
            spaceAfter=3,
        ),
        "code": ParagraphStyle(
            "code",
            parent=base["Code"],
            fontName=FONT_MONO,
            fontSize=7.0,
            leading=9.0,
            leftIndent=4,
            rightIndent=4,
            textColor=colors.HexColor("#0f172a"),
            backColor=colors.HexColor("#f1f5f9"),
            borderColor=colors.HexColor("#cbd5e1"),
            borderWidth=0.35,
            borderPadding=5,
            spaceBefore=4,
            spaceAfter=7,
        ),
        "toc": ParagraphStyle(
            "toc",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9,
            leading=12,
            leftIndent=10,
            spaceAfter=2,
        ),
    }


STYLES = styles()


def normalize(text: str) -> str:
    return (
        text.replace("\ufeff", "")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("\u2011", "-")
        .replace("\u00a0", " ")
    )


def clean_inline(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", rf'<font name="{FONT_BOLD}">\1</font>', escaped)
    return escaped


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(clean_inline(text), STYLES[style])


def parse_table(lines: list[str], doc_width: float) -> Table | None:
    rows: list[list[str]] = []
    for raw in lines:
        stripped = raw.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            return None
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)

    if not rows:
        return None

    width = max(len(row) for row in rows)
    for row in rows:
        row.extend([""] * (width - len(row)))

    if width == 1:
        col_widths = [doc_width]
    elif width == 2:
        col_widths = [doc_width * 0.32, doc_width * 0.68]
    elif width == 3:
        col_widths = [doc_width * 0.24, doc_width * 0.30, doc_width * 0.46]
    elif width == 4:
        col_widths = [doc_width * 0.19, doc_width * 0.22, doc_width * 0.29, doc_width * 0.30]
    else:
        col_widths = [doc_width / width] * width

    data = [[Paragraph(clean_inline(cell), STYLES["small"]) for cell in row] for row in rows]
    table = Table(data, colWidths=col_widths, repeatRows=1, splitByRow=1)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ]
        )
    )
    return table


def image_flowable(image_path: Path, doc_width: float, max_height: float = 11.2 * cm) -> list:
    if not image_path.exists():
        return [para(f"Brak obrazu: {image_path}", "body")]
    with PILImage.open(image_path) as im:
        width_px, height_px = im.size
    scale = min(doc_width / width_px, max_height / height_px, 1.0)
    width = width_px * scale
    height = height_px * scale
    return [Image(str(image_path), width=width, height=height), para(image_path.name, "caption")]


def parse_markdown(path: Path, doc_width: float) -> list:
    story: list = []
    lines = normalize(path.read_text(encoding="utf-8")).splitlines()
    index = 0
    in_code = False
    code_lines: list[str] = []

    while index < len(lines):
        line = lines[index].rstrip()

        if line.startswith("```"):
            if in_code:
                wrapped = []
                for code_line in code_lines:
                    wrapped.extend(textwrap.wrap(code_line, width=96, replace_whitespace=False) or [""])
                story.append(Preformatted("\n".join(wrapped), STYLES["code"]))
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue

        if in_code:
            code_lines.append(line)
            index += 1
            continue

        if not line.strip():
            story.append(Spacer(1, 3))
            index += 1
            continue

        if line.strip().startswith("|") and line.strip().endswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|") and lines[index].strip().endswith("|"):
                table_lines.append(lines[index])
                index += 1
            table = parse_table(table_lines, doc_width)
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 7))
            continue

        image_match = re.match(r"!\[([^\]]*)\]\(([^)]+)\)", line.strip())
        if image_match:
            image_rel = image_match.group(2)
            image_path = (path.parent / image_rel).resolve()
            story.extend(image_flowable(image_path, doc_width))
            index += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(clean_inline(line[2:]), STYLES["h1"]))
        elif line.startswith("## "):
            story.append(Paragraph(clean_inline(line[3:]), STYLES["h2"]))
        elif line.startswith("### "):
            story.append(Paragraph(clean_inline(line[4:]), STYLES["h3"]))
        elif re.match(r"^\s*[-*]\s+", line):
            text = re.sub(r"^\s*[-*]\s+", "", line)
            story.append(Paragraph(clean_inline(text), STYLES["bullet"], bulletText="-"))
        elif re.match(r"^\s*\d+\.\s+", line):
            number = re.match(r"^\s*(\d+)\.\s+", line).group(1)
            text = re.sub(r"^\s*\d+\.\s+", "", line)
            story.append(Paragraph(clean_inline(text), STYLES["bullet"], bulletText=f"{number}."))
        else:
            story.append(para(line))
        index += 1

    return story


def cover(doc_width: float) -> list:
    items: list = [
        Spacer(1, 2.4 * cm),
        Paragraph("AEIS SYSTEM BOOK 2026", STYLES["title"]),
        Paragraph("Pelna ksiega systemu: architektura, moduly, fazy, konfiguracja, funding, testy i screenshoty", STYLES["subtitle"]),
        Spacer(1, 0.5 * cm),
        para("Data wygenerowania: 2026-05-17", "subtitle"),
        para("Zrodlo: docs/aeis_full_documentation + runtime AEIS 3.5.0", "subtitle"),
        Spacer(1, 0.7 * cm),
    ]
    overview = SCREENSHOT_DIR / "00_overview.png"
    if overview.exists():
        items.extend(image_flowable(overview, doc_width, max_height=9.5 * cm))
    items.extend(
        [
            Spacer(1, 0.5 * cm),
            para("Zakres obejmuje backend FastAPI, frontend Next.js, menu operatora, lifecycle projektu 16-41, orchestration, memory, skills, funding, mobile, test center i polityke freeze.", "body"),
            para("Dokument jest snapshotem runtime lokalnego/dev-staging. Elementy produkcyjne, ktore nadal wymagaja hardeningu, sa opisane jawnie.", "body"),
            PageBreak(),
        ]
    )
    return items


def generated_toc() -> list:
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            name="TOCHeading1",
            fontName=FONT_BOLD,
            fontSize=9.5,
            leading=13,
            leftIndent=0,
            firstLineIndent=0,
            spaceBefore=3,
        ),
        ParagraphStyle(
            name="TOCHeading2",
            fontName=FONT,
            fontSize=8.2,
            leading=11,
            leftIndent=16,
            firstLineIndent=-8,
            spaceBefore=1,
        ),
    ]
    return [Paragraph("Spis tresci ksiegi", STYLES["h1"]), toc, PageBreak()]


def screenshot_gallery(doc_width: float) -> list:
    items: list = [Paragraph("Galeria screenshotow runtime", STYLES["h1"])]
    for image_path in sorted(SCREENSHOT_DIR.glob("*.png")):
        title = image_path.stem.replace("_", " ")
        items.append(Paragraph(clean_inline(title), STYLES["h2"]))
        items.extend(image_flowable(image_path, doc_width, max_height=12.5 * cm))
    items.append(PageBreak())
    return items


def draw_header_footer(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setFont(FONT, 7)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(doc.leftMargin, A4[1] - 1.05 * cm, "AEIS System Book 2026")
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.75 * cm, f"Strona {page}")
        canvas.setStrokeColor(colors.HexColor("#cbd5e1"))
        canvas.setLineWidth(0.25)
        canvas.line(doc.leftMargin, A4[1] - 1.18 * cm, A4[0] - doc.rightMargin, A4[1] - 1.18 * cm)
    canvas.restoreState()


class AeisBookTemplate(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph):
            style_name = flowable.style.name
            if style_name == "h1":
                self.notify("TOCEntry", (0, flowable.getPlainText(), self.page))
            elif style_name == "h2":
                self.notify("TOCEntry", (1, flowable.getPlainText(), self.page))


def build_pdf() -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = AeisBookTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=1.35 * cm,
        rightMargin=1.35 * cm,
        topMargin=1.55 * cm,
        bottomMargin=1.35 * cm,
        title="AEIS System Book 2026",
        author="Codex",
    )
    story: list = []
    story.extend(cover(doc.width))
    story.extend(generated_toc())
    for source in SOURCE_DOCS:
        story.append(Paragraph(clean_inline(source.stem.replace("_", " ")), STYLES["h1"]))
        story.extend(parse_markdown(source, doc.width))
        story.append(PageBreak())
    story.extend(screenshot_gallery(doc.width))
    doc.multiBuild(story, onFirstPage=draw_header_footer, onLaterPages=draw_header_footer)
    return OUTPUT_PDF


if __name__ == "__main__":
    print(build_pdf())
