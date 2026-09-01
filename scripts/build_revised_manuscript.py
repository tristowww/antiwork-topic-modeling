"""Create a dated manuscript revision from the retained source manuscript.

The original DOCX is never modified. This script copies its page system and
updates only the title, abstract, analysis sections, table, figures, and the
additional primary method references needed for the current BERTopic study.
"""
from __future__ import annotations

import re
import shutil
from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from docx.text.paragraph import Paragraph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "themesMngtGR_MitropoulosMinton.docx"
OUTPUT = ROOT / "deliverables" / "Antiwork_Topic_Modeling_Manuscript_REVISED_2026-09-01.docx"
FIGURES = ROOT / "outputs" / "v2_clean_min25" / "figures"


def set_text(paragraph: Paragraph, text: str, *, bold: bool = False, size: float = 12) -> None:
    """Replace text while keeping the source paragraph geometry intact."""
    paragraph.clear()
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(size)
    run.bold = bold


def add_reference_after(anchor: Paragraph, template: Paragraph, text: str) -> Paragraph:
    new_element = OxmlElement("w:p")
    if template._p.pPr is not None:
        new_element.append(deepcopy(template._p.pPr))
    anchor._p.addnext(new_element)
    paragraph = Paragraph(new_element, anchor._parent)
    set_text(paragraph, text)
    return paragraph


def shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell(cell, text: str, *, bold: bool = False, fill: str | None = None) -> None:
    if fill:
        shade(cell, fill)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    paragraph = cell.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    paragraph.paragraph_format.space_after = Pt(0)
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run._element.rPr.rFonts.set(qn("w:ascii"), "Times New Roman")
    run._element.rPr.rFonts.set(qn("w:hAnsi"), "Times New Roman")
    run.font.size = Pt(8.5)
    run.bold = bold


def set_table_widths(table, widths: list[int]) -> None:
    table.autofit = False
    table._tbl.tblPr.first_child_found_in("w:tblW").set(qn("w:w"), str(sum(widths)))
    table._tbl.tblPr.first_child_found_in("w:tblW").set(qn("w:type"), "dxa")
    for grid_col, width in zip(table._tbl.tblGrid.gridCol_lst, widths):
        grid_col.set(qn("w:w"), str(width))
    for row in table.rows:
        for cell, width in zip(row.cells, widths):
            tc_w = cell._tc.get_or_add_tcPr().first_child_found_in("w:tcW")
            tc_w.set(qn("w:w"), str(width))
            tc_w.set(qn("w:type"), "dxa")


def find_paragraph(doc: Document, starts_with: str) -> Paragraph:
    for paragraph in doc.paragraphs:
        if paragraph.text.startswith(starts_with):
            return paragraph
    raise ValueError(f"Could not find paragraph starting with {starts_with!r}")


def add_caption(doc: Document, label: str, text: str) -> None:
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(8)
    paragraph.paragraph_format.space_after = Pt(3)
    set_text(paragraph, label, bold=True)
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    set_text(paragraph, text)


def build() -> None:
    OUTPUT.parent.mkdir(exist_ok=True)
    shutil.copy2(SOURCE, OUTPUT)
    doc = Document(OUTPUT)
    paragraphs = doc.paragraphs

    set_text(paragraphs[1], "Manuscript draft")
    set_text(paragraphs[4], "Management-Related Discourse on r/antiwork, 2021-2025: An Exploratory Topic Modeling Study")
    set_text(paragraphs[7], "Management-Related r/antiwork Discourse")
    set_text(
        paragraphs[10],
        "This exploratory study examines management-related discussion in r/antiwork across four rolling years, from March 2021 through February 2025. We analyzed 97,254 posts that matched an established management-term filter using a BERTopic pipeline with sentence-transformer embeddings, UMAP, HDBSCAN, and class-based TF-IDF topic representations. The full-corpus model assigned 38.6% of posts to 199 non-outlier clusters. A documented codebook grouped 27 clusters into nine candidate themes, covering 18,506 posts (19.0% of the filtered corpus). Descriptive prevalence patterns show an early concentration of health, safety, and attendance discussion that declines over time, alongside a later rise in scheduling and time-off discussion. Compensation, career precarity, and recruitment remain present throughout the period. Findings are descriptive within the mapped subset and do not estimate sentiment, causal effects, or the full r/antiwork conversation.",
    )

    set_text(paragraphs[15], "Management-Related Discourse on r/antiwork, 2021-2025: An Exploratory Topic Modeling Study")
    set_text(
        paragraphs[17],
        "This paper approaches the study of employee discontent in the Great Resignation through the lens of management-related public discourse. Building on earlier work that examined r/antiwork during the first year of the Great Resignation, the present study uses four years of posts to describe candidate themes in management-related discussion. Social media posts provide a large and naturally occurring text source, but they do not reveal individual motives for turnover or provide a representative sample of employees. Accordingly, this study treats observed topic patterns as exploratory signals rather than evidence of the causes of resignation or retention.",
    )
    set_text(
        paragraphs[20],
        "Text analysis can support exploratory research by identifying patterns in how people discuss a topic without requiring categories to be fixed in advance (Grimmer & Stewart, 2013; Schwartz & Ungar, 2015). Contemporary topic-modeling workflows can combine contextual sentence embeddings with dimensionality reduction, density-based clustering, and topic representations to generate inspectable candidate themes. In this study, we use that approach to describe management-related r/antiwork discourse over four rolling years while preserving explicit limits on coverage and interpretation.",
    )
    set_text(
        paragraphs[31],
        "The present study extends the original one-year exploration of management-related r/antiwork discourse into a four-year descriptive analysis. Rather than treating the earlier six-topic LDA solution as a model to reproduce, we use an embedding-based topic-modeling pipeline to identify candidate themes in title-plus-body text and to describe how their prevalence changes across four rolling March-to-February windows. The earlier study provides historical context; the present analysis is designed to identify bounded, reproducible patterns in the documented theme map.",
    )
    set_text(
        paragraphs[32],
        "Research Question: Across management-related r/antiwork posts from March 2021 through February 2025, what candidate themes are identifiable in an exploratory BERTopic map, and how do their descriptive prevalence patterns vary across four rolling yearly windows?",
        bold=True,
    )

    set_text(paragraphs[34], "Corpus and Sampling", bold=True)
    set_text(
        paragraphs[35],
        "We analyzed 97,254 unique r/antiwork posts dated from March 2021 through February 2025 that matched the study's existing management-related filter (boss, manager, supervisor, or team lead variants). The frozen input and preprocessed corpus contained identical post-id sets, and every retained post re-matched the filter. The analytic text combined title and body after placeholder handling; posts with deleted or removed content were retained when usable title or body text remained. The corpus is a filtered public-discourse sample, not a representative sample of workers or a measure of individual employee attitudes.",
    )
    set_text(paragraphs[36], "Data Preparation and Time Windows", bold=True)
    set_text(
        paragraphs[37],
        "The primary representation was title-plus-body text. Four contiguous rolling windows were defined as Y1 (March 2021-February 2022), Y2 (March 2022-February 2023), Y3 (March 2023-February 2024), and Y4 (March 2024-February 2025). Candidate-theme prevalence was calculated as the number of posts assigned to the included theme clusters divided by every filtered post in the same window. Thus, reported values describe the mapped subset of the filtered corpus rather than all potentially relevant management discussion.",
    )
    set_text(paragraphs[38], "Topic Modeling and Codebook", bold=True)
    set_text(
        paragraphs[39],
        "We fit a full-corpus BERTopic model using all-MiniLM-L6-v2 sentence-transformer embeddings, UMAP dimensionality reduction, HDBSCAN density-based clustering, and class-based TF-IDF topic representations (Grootendorst, 2022; McInnes et al., 2017, 2018; Reimers & Gurevych, 2019). The model produced 199 non-outlier clusters and assigned 37,536 posts (38.6% of the corpus) to those clusters. We reviewed the 30 largest clusters and documented a 27-cluster, nine-theme candidate codebook; generic, deleted, and community-meta clusters were excluded. The included clusters contain 18,506 posts, or 19.0% of all filtered posts and 49.3% of assigned posts.",
    )
    set_text(
        paragraphs[40],
        "We treated the theme map as exploratory and tested the boundaries of that interpretation. A frozen-corpus audit confirmed matching post ids and the management-term filter. Three UMAP seeds on the same 10,000-post stratified sample produced all-document adjusted Rand indices of 0.721 to 0.770 and joint-inlier indices of 0.900 to 0.966. A titles-only sensitivity analysis produced a materially different partition, so title-plus-body remains the primary representation. Cross-window term alignment is reported as supporting context only. We do not report sentiment results or causal inferences.",
    )

    set_text(paragraphs[42], "The model's coverage is central to interpreting the results. Of 97,254 filtered posts, 37,536 (38.6%) received non-outlier cluster assignments; the finalized nine-theme codebook covers 18,506 posts (19.0% of all filtered posts). Assignment coverage varied from 33.1% to 44.0% by month (Figure 1). HDBSCAN outliers are therefore treated as a coverage limitation rather than a substantive category. Table 1 reports candidate-theme prevalence by rolling window using all filtered posts in each window as the denominator.")
    set_text(paragraphs[43], "Within the mapped subset, health, safety, and attendance discussion declined from 4.97% of Y1 posts to 2.50% in Y4, reflecting an early concentration of COVID- and illness-related clusters. Scheduling, hours, and time-off discussion increased from 1.71% to 3.20% and was the largest mapped theme in Y4. Workplace authority and interpersonal conflict also increased from 0.74% to 2.06%. Compensation and pay rights remained substantial in all windows, while career precarity and exit remained broadly stable. These are descriptive changes in the documented candidate-theme map, not evidence that the full r/antiwork conversation or workers' underlying experiences changed by the same amount.")
    paragraphs[41].paragraph_format.space_after = Pt(6)
    paragraphs[42].paragraph_format.space_before = Pt(0)
    paragraphs[42].paragraph_format.keep_with_next = False
    paragraphs[43].paragraph_format.keep_with_next = False

    set_text(paragraphs[45], "The updated analysis supports a narrower conclusion than the original one-year LDA account: management-related r/antiwork discussion changed in composition across the four rolling windows within a limited, auditable theme map. The early prominence of health, safety, and attendance content is consistent with the timing of COVID- and illness-related discussion, whereas the later prominence of scheduling and time-off clusters points to a different set of recurring concerns. The study does not establish why these patterns changed or whether they generalize beyond the sampled forum.")
    set_text(paragraphs[46], "Compensation, career precarity and exit, and recruitment-related discussion remain visible across the observation period. That persistence should be read as evidence that these themes continue to appear in the mapped subset, not as a claim that any concern is universally salient or unchanged in the broader labor force. Similarly, the increase in workplace authority and interpersonal-conflict clusters provides a candidate pattern for future investigation rather than a population estimate.")
    set_text(paragraphs[47], "The results are most useful as a longitudinal descriptive extension of the earlier study. They show that a modern semantic topic-modeling workflow can separate candidate streams such as scheduling and time off, health and attendance, compensation, career precarity, workplace authority, collective power, and service work. The codebook, coverage metrics, and sensitivity results make those interpretations inspectable, but they do not turn the clusters into a final taxonomy or validate individual post labels as ground truth.")
    set_text(paragraphs[48], "")
    set_text(paragraphs[49], "")
    set_text(paragraphs[50], "Practical Implications", bold=True)
    set_text(paragraphs[51], "The findings should be used as a source of questions for organizational listening and research, not as direct policy prescriptions. The recurring visibility of scheduling, time-off, compensation, and workplace-control discussion suggests that these are useful domains to examine with representative employee data and context-specific measures. Organizations should not infer turnover effects, employee sentiment, or causal priorities from this public-discourse analysis alone.")
    set_text(paragraphs[52], "Strengths, Limitations, and Future Research", bold=True)
    set_text(paragraphs[53], "The study combines a four-year frozen corpus, document-level assignments, a documented codebook, explicit denominators, and completed robustness checks. Key limitations are the 61.4% HDBSCAN outlier rate, 19.0% theme-map coverage, 1.2% residual duplicate text, title-only sensitivity, and the management-related sampling frame. Future work could extend the codebook or test a saved-model sensitivity analysis; neither sentiment nor causal claims are part of this exploratory paper.")
    paragraphs[50].paragraph_format.space_after = Pt(6)
    paragraphs[51].paragraph_format.keep_with_next = False
    paragraphs[52].paragraph_format.space_after = Pt(6)
    paragraphs[53].paragraph_format.keep_with_next = False

    old_table = doc.tables[0]
    old_table._element.getparent().remove(old_table._element)
    set_text(paragraphs[89], "Table 1", bold=True)
    set_text(paragraphs[91], "Candidate Theme Prevalence by Rolling Window", bold=True)
    table = doc.add_table(rows=1, cols=5)
    set_table_widths(table, [2520, 900, 900, 900, 4140])
    headers = ["Candidate theme", "Y1", "Y4", "Change", "Descriptive pattern"]
    for cell, value in zip(table.rows[0].cells, headers):
        set_cell(cell, value, bold=True, fill="D9E2F3")
    values = [
        ("Health, safety, and attendance", "4.97%", "2.50%", "-2.47 pp", "Early COVID- and illness-related concentration contracts."),
        ("Scheduling, hours, and time off", "1.71%", "3.20%", "+1.49 pp", "Increases across the windows; largest mapped theme in Y4."),
        ("Workplace authority and interpersonal conflict", "0.74%", "2.06%", "+1.32 pp", "Increases in the mapped conflict and performance-review clusters."),
        ("Compensation and pay rights", "3.52%", "3.04%", "-0.48 pp", "Remains substantial in every window after a Y2 high."),
        ("Career precarity and exit", "2.54%", "2.47%", "-0.07 pp", "Broadly stable across the four windows."),
        ("Recruitment and labor market", "1.98%", "2.33%", "+0.35 pp", "Persistent with a modest net increase."),
        ("Work arrangements and control", "1.01%", "1.35%", "+0.34 pp", "Remains present; remote/RTO is a distinct stream."),
        ("Collective worker power and rights", "0.82%", "0.42%", "-0.40 pp", "Declines after the earlier unionization peak in the mapped subset."),
        ("Service work and tips", "1.32%", "0.93%", "-0.39 pp", "Declines in the mapped subset; codebook notes lexical noise."),
    ]
    for row_values in values:
        cells = table.add_row().cells
        for cell, value in zip(cells, row_values):
            set_cell(cell, value)

    add_caption(doc, "Figure 1", "Monthly BERTopic assignment coverage. Outliers are a coverage limitation, not a substantive category.")
    doc.add_picture(str(FIGURES / "monthly_assignment_coverage.png"), width=Inches(6.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_caption(doc, "Figure 2", "Candidate-theme prevalence by rolling window. Shares use all filtered posts in each window as the denominator.")
    doc.add_picture(str(FIGURES / "candidate_theme_rolling_window_prevalence.png"), width=Inches(6.0))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    reference_template = find_paragraph(doc, "Bacon, T. R.")
    grimmer = find_paragraph(doc, "Grimmer, J.")
    grootendorst = add_reference_after(grimmer, reference_template, "Grootendorst, M. (2022). BERTopic: Neural topic modeling with a class-based TF-IDF procedure. arXiv. https://doi.org/10.48550/arXiv.2203.05794")
    mcfeely = find_paragraph(doc, "McFeely, S.")
    hdbscan = add_reference_after(mcfeely, reference_template, "McInnes, L., Healy, J., & Astels, S. (2017). hdbscan: Hierarchical density based clustering. Journal of Open Source Software, 2(11), 205. https://doi.org/10.21105/joss.00205")
    add_reference_after(hdbscan, reference_template, "McInnes, L., Healy, J., Saul, N., & Grossberger, L. (2018). UMAP: Uniform Manifold Approximation and Projection. Journal of Open Source Software, 3(29), 861. https://doi.org/10.21105/joss.00861")
    reddit_moderator = find_paragraph(doc, "Reddit Staff. (2022")
    add_reference_after(reddit_moderator, reference_template, "Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. In Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing and the 9th International Joint Conference on Natural Language Processing (EMNLP-IJCNLP) (pp. 3982-3992). Association for Computational Linguistics. https://doi.org/10.18653/v1/D19-1410")

    reference_heading = find_paragraph(doc, "References")
    reference_heading.paragraph_format.keep_with_next = True
    main_text = []
    started = False
    for paragraph in doc.paragraphs:
        if paragraph is reference_heading:
            break
        if paragraph.text.startswith("Management-Related Discourse"):
            started = True
        if started:
            main_text.append(paragraph.text)
    word_count = len(re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", " ".join(main_text)))
    set_text(paragraphs[13], f"{word_count:,} (main text; references, table, and figure captions excluded)")

    for paragraph in (paragraphs[56], paragraphs[55], paragraphs[54]):
        paragraph._element.getparent().remove(paragraph._element)

    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
