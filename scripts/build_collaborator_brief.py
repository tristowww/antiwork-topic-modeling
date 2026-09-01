"""Build the collaborator-ready exploratory analysis brief.

The brief only uses aggregate, shareable evidence. Raw post text, sampled
excerpts, embeddings, and local-only analysis artifacts are intentionally absent.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "deliverables"
OUT_DOCX = OUT_DIR / "Antiwork_Exploratory_Analysis_Brief.docx"
REPO_URL = "https://github.com/tristowww/antiwork-topic-modeling"

NAVY = "17365D"
BLUE = "2E74B5"
MID_BLUE = "4978A8"
MUTED = "5D6B7A"
LIGHT_BLUE = "E8EEF5"
LIGHT_GRAY = "F2F4F7"
WHITE = "FFFFFF"
INK = "1F2937"


def set_run(run, size: float = 11, color: str = INK, bold: bool = False, italic: bool = False) -> None:
    run.font.name = "Calibri"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    element = tc_pr.find(qn("w:shd"))
    if element is None:
        element = OxmlElement("w:shd")
        tc_pr.append(element)
    element.set(qn("w:fill"), fill)


def set_cell_margins(cell) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    margins = tc_pr.first_child_found_in("w:tcMar")
    if margins is None:
        margins = OxmlElement("w:tcMar")
        tc_pr.append(margins)
    for side, value in {"top": 80, "start": 120, "bottom": 80, "end": 120}.items():
        node = margins.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            margins.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_widths(table, widths: list[int]) -> None:
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table._tbl.tblPr.first_child_found_in("w:tblW").set(qn("w:w"), str(sum(widths)))
    table._tbl.tblPr.first_child_found_in("w:tblW").set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for col, width in zip(grid.gridCol_lst, widths):
        col.set(qn("w:w"), str(width))
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            cell.width = Inches(width / 1440)
            tc_w = cell._tc.get_or_add_tcPr().first_child_found_in("w:tcW")
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER


def paragraph(doc, text: str = "", *, size: float = 10.5, color: str = INK, bold: bool = False, italic: bool = False, after: float = 6, style: str = "Normal"):
    p = doc.add_paragraph(style=style)
    if text:
        set_run(p.add_run(text), size, color, bold, italic)
    p.paragraph_format.space_after = Pt(after)
    return p


def heading(doc, text: str, level: int = 1) -> None:
    p = doc.add_paragraph(style=f"Heading {level}")
    set_run(p.add_run(text), 15 if level == 1 else 12.5, NAVY, True)


def bullet(doc, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    set_run(p.add_run(text), 10.2)


def hyperlink(paragraph_obj, text: str, url: str) -> None:
    relation_id = paragraph_obj.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), relation_id)
    run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), BLUE)
    r_pr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    r_pr.append(underline)
    run.append(r_pr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    link.append(run)
    paragraph_obj._p.append(link)


def callout_pair(doc, left_title: str, left_text: str, right_title: str, right_text: str) -> None:
    table = doc.add_table(rows=1, cols=2)
    set_table_widths(table, [4680, 4680])
    for cell, title, body in zip(table.rows[0].cells, (left_title, right_title), (left_text, right_text)):
        shade(cell, "FAFBFC")
        set_run(cell.paragraphs[0].add_run(title), 9.6, NAVY, True)
        p = cell.add_paragraph()
        set_run(p.add_run(body), 9.2)


def metric_strip(doc) -> None:
    table = doc.add_table(rows=1, cols=4)
    set_table_widths(table, [2340, 2340, 2340, 2340])
    for cell, (value, label) in zip(table.rows[0].cells, [
        ("97,254", "filtered posts"),
        ("199", "non-outlier clusters"),
        ("38.6%", "topic assignment"),
        ("19.0%", "theme-map coverage"),
    ]):
        shade(cell, "FAFBFC")
        cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(cell.paragraphs[0].add_run(value), 13, NAVY, True)
        p = cell.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(p.add_run(label), 8.3, MUTED)


def findings_table(doc) -> None:
    table = doc.add_table(rows=1, cols=4)
    set_table_widths(table, [3300, 1500, 1500, 3060])
    for cell, label in zip(table.rows[0].cells, ["Theme", "Y1", "Y4", "Interpretation"]):
        shade(cell, LIGHT_BLUE)
        set_run(cell.paragraphs[0].add_run(label), 9, NAVY, True)
    rows = [
        ("Health safety and attendance", "4.97%", "2.50%", "Down 2.47 pp; early COVID/illness concentration contracts."),
        ("Scheduling hours and time off", "1.71%", "3.20%", "Up 1.49 pp; largest mapped theme in Y4."),
        ("Compensation and pay rights", "3.52%", "3.04%", "Remains substantial in every window after a Y2 high."),
        ("Career precarity and exit", "2.54%", "2.47%", "Broadly stable across four rolling windows."),
    ]
    for index, row in enumerate(rows):
        cells = table.add_row().cells
        if index % 2:
            for cell in cells:
                shade(cell, "FAFBFC")
        for cell, value in zip(cells, row):
            set_run(cell.paragraphs[0].add_run(value), 8.5)


def robustness_table(doc) -> None:
    table = doc.add_table(rows=1, cols=2)
    set_table_widths(table, [2500, 6860])
    for cell, label in zip(table.rows[0].cells, ["Check", "Result"]):
        shade(cell, LIGHT_BLUE)
        set_run(cell.paragraphs[0].add_run(label), 9, NAVY, True)
    rows = [
        ("Corpus audit", "Inputs contain 97,254 matching unique post IDs; the management-term filter re-matches 100% of retained posts."),
        ("Seed stability", "Across three UMAP seeds on the same 10,000-post stratified sample, joint-inlier ARI was 0.900 to 0.966."),
        ("Window alignment", "Conservative one-to-one term matching is supporting context, not proof of substantive persistence."),
        ("Text sensitivity", "Titles-only clustering was stable but materially different from title-plus-body; title-plus-body remains the primary representation."),
    ]
    for index, (label, result) in enumerate(rows):
        cells = table.add_row().cells
        if index % 2:
            for cell in cells:
                shade(cell, "FAFBFC")
        set_run(cells[0].paragraphs[0].add_run(label), 8.5, NAVY, True)
        set_run(cells[1].paragraphs[0].add_run(result), 8.5)


def configure(doc: Document) -> None:
    doc.settings.odd_and_even_pages_header_footer = True
    section = doc.sections[0]
    section.top_margin = Inches(0.76)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.82)
    section.right_margin = Inches(0.82)
    section.header_distance = Inches(0.28)
    section.footer_distance = Inches(0.28)
    for header in (section.header, section.even_page_header):
        h = header.paragraphs[0]
        h.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        set_run(h.add_run("Antiwork topic modeling | Analysis brief"), 8.2, MUTED, False)
    for footer in (section.footer, section.even_page_footer):
        f = footer.paragraphs[0]
        f.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run(f.add_run("Prepared 1 September 2026 | Exploratory evidence package"), 8.2, MUTED)
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.1
    for level, size, before, after, color in ((1, 15, 12, 6, NAVY), (2, 12.5, 9, 4, NAVY), (3, 11.5, 7, 3, NAVY)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.color.rgb = RGBColor.from_string(color)
        style.font.bold = True
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)


def build() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    doc = Document()
    configure(doc)
    paragraph(doc, "Analysis brief", size=9.2, color=MUTED, after=3)
    paragraph(doc, "Antiwork Topic Modeling", size=22, color=NAVY, bold=True, after=2)
    paragraph(doc, "Exploratory longitudinal analysis for collaborator review", size=11.5, color=MUTED, after=12)
    metric_strip(doc)
    heading(doc, "Study summary")
    paragraph(doc, "Across 97,254 management-related r/antiwork posts from March 2021 through February 2025, the updated BERTopic analysis identifies a descriptive shift away from COVID-centered health and safety discussion and toward scheduling and time-off discussion. Compensation, career precarity, and recruitment remain present across the four rolling windows.")
    callout_pair(doc, "Completed analysis", "Rebuilt the analysis with BERTopic; exported document-level assignments and four rolling-window fits; finalized a 27-cluster, nine-theme codebook; and produced figures and reproducibility materials.", "Interpretive scope", "The findings describe prevalence patterns within the documented theme map. They do not support causal claims, full-conversation prevalence estimates, or sentiment conclusions.")
    heading(doc, "Selected findings")
    findings_table(doc)
    paragraph(doc, "All percentages use every filtered post in each rolling window as the denominator. They describe the mapped subset, not all potentially relevant content in the corpus.", size=8.5, color=MUTED, italic=True, after=4)
    heading(doc, "Data collection", 2)
    paragraph(doc, "Public r/antiwork submissions were retrieved through the Arctic Shift archive API in monthly UTC batches from 1 March 2021 through 1 March 2025. The analysis retained unique posts whose title or body matched the established management terms boss, manager, supervisor, or team lead, including plural variants. The resulting corpus is an archive-based sample of public discourse, not a representative sample of employees or an author-level panel.", size=9.1, after=0)
    doc.add_page_break()

    heading(doc, "Analytic workflow")
    paragraph(doc, "The analysis proceeded as follows. Corpus checks, model-based topic discovery, descriptive prevalence estimates, and robustness evidence are reported separately.", size=9.5, color=MUTED, after=8)
    steps = [
        ("Freeze and audit the corpus", "Matched the management-related filter to the preprocessed analysis corpus and confirmed 97,254 unique post IDs. A duplicate audit found 1.2% residual duplicate non-placeholder texts; this is reported rather than silently removed."),
        ("Construct the primary text field", "Used post title plus body after handling deleted and placeholder content. A title-only run was retained as a sensitivity analysis, not substituted for the primary representation."),
        ("Discover topics with a current topic-modeling pipeline", "Embedded documents with all-MiniLM-L6-v2, reduced the embedding space with UMAP, clustered with HDBSCAN, and represented topics with BERTopic c-TF-IDF. The full-corpus model produced 199 non-outlier clusters and assigned 38.6% of posts."),
        ("Document the theme map", "Reviewed the largest 30 clusters and retained 27 interpretable clusters in a nine-theme candidate codebook. Generic, deleted, and community-meta clusters were excluded, yielding 18,506 mapped posts (19.0% of the full filtered corpus)."),
        ("Estimate descriptive longitudinal patterns", "Calculated each theme's share of every filtered post in four March-to-February rolling windows. Figure 1 shows the resulting exploratory prevalence patterns; Figure 2 shows monthly assignment coverage so the mapped share is visible."),
        ("Test stability and state the boundary", "Ran seed-stability checks, title-only sensitivity, and unique-post overlap checks across rolling windows. Sentiment was intentionally not analyzed, and the paper will make no causal or full-conversation prevalence claims."),
    ]
    for number, (title, detail) in enumerate(steps, start=1):
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(6)
        set_run(p.add_run(f"{number}. {title}. "), 10.0, NAVY, True)
        set_run(p.add_run(detail), 9.5, INK)
    paragraph(doc, "The repository includes the reproducible scripts, codebook, diagnostics, and aggregate evidence used in this brief.", size=8.6, color=MUTED, italic=True, after=0)
    doc.add_page_break()

    doc.add_picture(str(ROOT / "outputs" / "v2_clean_min25" / "figures" / "candidate_theme_rolling_window_prevalence.png"), width=Inches(4.55))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph(doc, "Figure 1. Exploratory prevalence by rolling window. The 27-cluster map excludes generic, deleted, and community-meta clusters.", size=8.2, color=MUTED, italic=True, after=0)

    heading(doc, "Analytic approach and scope")
    callout_pair(doc, "Primary analysis", "Sentence-transformer embeddings (all-MiniLM-L6-v2), UMAP, HDBSCAN, BERTopic topic representations, and a full-corpus model for longitudinal prevalence. Per-window fits serve as stability diagnostics.", "Coverage of estimates", "The model assigns 38.6% of posts to non-outlier clusters. The final theme map covers 18,506 posts: 19.0% of all filtered posts and 49.3% of assigned posts.")
    heading(doc, "Assignment coverage", 2)
    doc.add_picture(str(ROOT / "outputs" / "v2_clean_min25" / "figures" / "monthly_assignment_coverage.png"), width=Inches(5.8))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph(doc, "Figure 2. Assignment coverage varied from 33.1% to 44.0% by month. Outliers are a coverage limitation, not a substantive category.", size=8.2, color=MUTED, italic=True)
    doc.add_page_break()
    heading(doc, "Robustness checks", 2)
    robustness_table(doc)
    paragraph(doc, "A larger all-mpnet-base-v2 encoder check was attempted but did not complete within the available CPU bound, so it is deferred and not treated as evidence.", size=8.5, color=MUTED, italic=True)

    heading(doc, "Interpreting the results", 2)
    callout_pair(doc, "Observed patterns", "Within the mapped themes, health, safety, and attendance discussion declined over the four windows, while scheduling, hours, and time-off discussion increased. Compensation, career precarity, and recruitment remained visible throughout.", "What the results support", "These patterns describe changes in the composition of management-related public discussion. They identify domains for follow-up with representative employee data; they do not establish employee sentiment, turnover drivers, or policy effects.")

    heading(doc, "Remaining work")
    callout_pair(doc, "Available for drafting", "Results, figures, a theme codebook, coverage diagnostics, seed stability, text-mode sensitivity, and a defined interpretive scope are ready for the manuscript.", "Optional extensions", "Sentiment annotation, a larger codebook, saved-model refit, TopicGPT comparison, and the MPNet check are possible extensions, but are not required for this exploratory paper.")
    heading(doc, "Manuscript revision status", 2)
    callout_pair(doc, "Sections revised", "The revised manuscript includes the title and abstract; current-study framing and research question; Methods, Results, Discussion, implications, limitations; figures; and primary BERTopic references.", "Before circulation", "Harmonize retained Background language with the paper's exploratory, descriptive scope. Historical theory and prior turnover findings should remain context, not claims tested by this study.")
    heading(doc, "Materials for drafting", 2)
    paragraph(doc, "Draft in this order: method and sampling frame; coverage and descriptive results; limitations; then an exploratory discussion. Use the documented theme map and avoid causal, full-conversation, or sentiment claims.", size=9.4, after=4)
    p = paragraph(doc, "Reproducible code and shareable evidence: ", size=9.4, after=4)
    hyperlink(p, REPO_URL, REPO_URL)
    paragraph(doc, "Method records: planning/SCRAPING.md, planning/PREPROCESSING.md, planning/WRITING_HANDOFF.md, planning/ROBUSTNESS.md, and planning/CANDIDATE_THEME_CODEBOOK.csv.", size=8.4, color=MUTED, after=3)
    paragraph(doc, "Current status: the analysis package is complete and ready for drafting as a descriptive, exploratory topic-prevalence study.", size=9.4, color=NAVY, bold=True)
    doc.save(OUT_DOCX)
    print(OUT_DOCX)


if __name__ == "__main__":
    build()
