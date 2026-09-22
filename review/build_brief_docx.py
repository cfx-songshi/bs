"""Turn the page-by-page brief from Markdown into Word.

The brief is the document the deck is defended with, and reviewers ask for it as .docx.
It is generated from the same Markdown that sits next to the deck rather than kept as a
second copy, because the two drift apart the moment one is edited by hand — the brief and
the deck have to be rewritten together (see 阶段汇报_正文备注与讲解稿审核.md).

The Markdown subset the brief uses is small: headings, bold/italic/code spans, links,
tables with an alignment row, ordered and bullet lists, and one blockquote for wording
that is meant to be quoted. Each is handled explicitly below; anything else falls through
to a plain paragraph, which is the safe default for a document that will be read.

Run:  python review/build_brief_docx.py

Needs python-docx (pip install python-docx); the rest of review/ only needs python-pptx,
matplotlib and pymupdf.
"""

import os
import re
import sys

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.shared import Cm, Pt, RGBColor

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '阶段仿真实现汇报_逐页讲解与论文对应.md')
OUT = os.path.join(HERE, '阶段仿真实现汇报_逐页讲解与论文对应.docx')

FONT = 'Microsoft YaHei'
MONO = 'Consolas'
INK = RGBColor(0x1F, 0x24, 0x2B)
MUTED = RGBColor(0x5A, 0x63, 0x6E)
BRAND = RGBColor(0x1F, 0x4E, 0x79)
CODE = RGBColor(0xA3, 0x3B, 0x2E)
LINK = RGBColor(0x0B, 0x5F, 0xB5)

BODY_SIZE = 10.5
TABLE_SIZE = 9.0
USABLE_CM = 16.6

# Inline spans, longest marker first so that ** is never read as two italic stars.
SPAN = re.compile(r'(\*\*.+?\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\*[^*\n]+\*)')
LINK_SPAN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def set_font(run, size, bold=False, italic=False, color=None, font=FONT):
    """Set a run's font, East Asian face included.

    Setting font.name alone writes only the latin typeface and Word then picks its own CJK
    face, which is how the deck ended up in a font mixture nobody chose.
    """
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color if color is not None else INK
    run.font.name = font
    properties = run._element.get_or_add_rPr()
    fonts = properties.find(qn('w:rFonts'))
    if fonts is None:
        fonts = OxmlElement('w:rFonts')
        properties.append(fonts)
    for attribute in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
        fonts.set(qn(attribute), font)


def add_hyperlink(paragraph, url, text, size=BODY_SIZE):
    """A real Word hyperlink, so the file paths in the evidence list stay clickable."""
    link = OxmlElement('w:hyperlink')
    link.set(qn('r:id'), paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True))
    run = OxmlElement('w:r')
    link.append(run)
    paragraph._p.append(link)
    from docx.text.run import Run
    handle = Run(run, paragraph)
    handle.text = text
    set_font(handle, size, color=LINK)
    handle.font.underline = True
    return handle


def add_spans(paragraph, text, size=BODY_SIZE):
    """Write text with its inline bold / italic / code / link markup resolved."""
    for piece in SPAN.split(text):
        if not piece:
            continue
        if piece.startswith('**') and piece.endswith('**') and len(piece) > 4:
            run = paragraph.add_run(piece[2:-2])
            set_font(run, size, bold=True)
        elif piece.startswith('`') and piece.endswith('`') and len(piece) > 2:
            run = paragraph.add_run(piece[1:-1])
            set_font(run, size - 0.5, color=CODE, font=MONO)
        else:
            match = LINK_SPAN.fullmatch(piece)
            if match:
                add_hyperlink(paragraph, match.group(2), match.group(1), size)
            elif piece.startswith('*') and piece.endswith('*') and len(piece) > 2:
                run = paragraph.add_run(piece[1:-1])
                set_font(run, size, italic=True)
            else:
                run = paragraph.add_run(piece)
                set_font(run, size)


def shade(cell_or_paragraph, fill):
    """Light grey fills, used for table headers and the quoted wording."""
    element = OxmlElement('w:shd')
    element.set(qn('w:val'), 'clear')
    element.set(qn('w:color'), 'auto')
    element.set(qn('w:fill'), fill)
    if hasattr(cell_or_paragraph, '_tc'):
        cell_or_paragraph._tc.get_or_add_tcPr().append(element)
    else:
        cell_or_paragraph._p.get_or_add_pPr().append(element)


def split_row(line):
    return [cell.strip() for cell in line.strip().strip('|').split('|')]


def is_delimiter(line):
    return bool(re.fullmatch(r'\|[\s\-:|]+\|', line.strip()))


def column_fractions(count):
    """Column widths as fractions of the text column, widest column last."""
    if count == 2:
        return [0.42, 0.58]
    if count == 3:
        return [0.28, 0.34, 0.38]
    if count == 4:
        return [0.23, 0.25, 0.25, 0.27]
    return [1.0 / count] * count


def add_table(doc, header, rows, aligns=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    fractions = column_fractions(len(header))
    widths = [Cm(USABLE_CM * fraction) for fraction in fractions]

    for index, text in enumerate(header):
        cell = table.cell(0, index)
        shade(cell, '1F4E79')
        paragraph = cell.paragraphs[0]
        paragraph.paragraph_format.space_after = Pt(1)
        for piece in SPAN.split(text):
            if not piece:
                continue
            run = paragraph.add_run(piece.strip('*`'))
            set_font(run, TABLE_SIZE, bold=True, color=RGBColor(0xFF, 0xFF, 0xFF))

    for row_index, values in enumerate(rows, start=1):
        for column, text in enumerate(values):
            cell = table.cell(row_index, column)
            if row_index % 2 == 0:
                shade(cell, 'F2F4F7')
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(1)
            if aligns and aligns[column] == 'right':
                paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            add_spans(paragraph, text, TABLE_SIZE)

    for row in table.rows:
        for index, cell in enumerate(row.cells):
            cell.width = widths[index]
    return table


def add_body(doc, text, indent=None, quoted=False, size=BODY_SIZE):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.3
    if indent is not None:
        paragraph.paragraph_format.left_indent = Cm(indent)
        paragraph.paragraph_format.first_line_indent = Cm(-indent)
    if quoted:
        paragraph.paragraph_format.left_indent = Cm(0.5)
        paragraph.paragraph_format.right_indent = Cm(0.5)
        paragraph.paragraph_format.space_before = Pt(4)
        paragraph.paragraph_format.space_after = Pt(8)
        shade(paragraph, 'F4F6F9')
    add_spans(paragraph, text, size)
    return paragraph


def add_heading(doc, text, level):
    settings = {1: (18.0, BRAND), 2: (14.0, BRAND), 3: (12.0, MUTED)}
    size, color = settings[level]
    paragraph = doc.add_heading('', level=level)
    paragraph.paragraph_format.space_before = Pt(14 if level > 1 else 0)
    paragraph.paragraph_format.space_after = Pt(6)
    add_spans(paragraph, text, size)
    for run in paragraph.runs:
        set_font(run, size, bold=True, color=color)
    return paragraph


def build():
    with open(SRC, encoding='utf-8') as handle:
        lines = handle.read().splitlines()

    doc = Document()
    section = doc.sections[0]
    for margin in ('top_margin', 'bottom_margin'):
        setattr(section, margin, Cm(2.2))
    for margin in ('left_margin', 'right_margin'):
        setattr(section, margin, Cm(2.2))
    normal = doc.styles['Normal']
    normal.font.size = Pt(BODY_SIZE)
    normal.font.name = FONT
    normal.element.rPr.rFonts.set(qn('w:eastAsia'), FONT)

    counts = {'heading': 0, 'table': 0, 'quote': 0, 'item': 0}
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        if not stripped:
            index += 1
            continue

        if stripped.startswith('|') and index + 1 < len(lines) and is_delimiter(lines[index + 1]):
            header = split_row(stripped)
            aligns = []
            for spec in split_row(lines[index + 1]):
                aligns.append('right' if spec.endswith(':') else 'left')
            index += 2
            rows = []
            while index < len(lines) and lines[index].strip().startswith('|'):
                rows.append(split_row(lines[index]))
                index += 1
            add_table(doc, header, rows, aligns)
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
            counts['table'] += 1
            continue

        heading = re.match(r'^(#{1,4})\s+(.*)$', stripped)
        if heading:
            add_heading(doc, heading.group(2), min(len(heading.group(1)), 3))
            counts['heading'] += 1
            index += 1
            continue

        if stripped.startswith('> '):
            add_body(doc, stripped[2:].strip(), quoted=True)
            counts['quote'] += 1
            index += 1
            continue

        ordered = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if ordered:
            add_body(doc, '%s. %s' % (ordered.group(1), ordered.group(2)), indent=0.75)
            counts['item'] += 1
            index += 1
            continue

        if stripped.startswith('- '):
            add_body(doc, '· ' + stripped[2:].strip(), indent=0.55)
            counts['item'] += 1
            index += 1
            continue

        add_body(doc, stripped)
        index += 1

    doc.save(OUT)
    print('wrote %s (%.2f MB, %d headings, %d tables, %d list items, %d quotes)'
          % (OUT, os.path.getsize(OUT) / 1e6, counts['heading'], counts['table'],
             counts['item'], counts['quote']))
    return counts


if __name__ == '__main__':
    build()
    sys.exit(0)
