from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
import re

def _iter_block_items(doc):

    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _table_rows_text(table: Table) -> list[str]:

    rows = [[cell.text.strip() for cell in row.cells] for row in table.rows]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []

    header, *body_rows = rows
    if not body_rows:
        return [" | ".join(header)]

    texts = []
    for row in body_rows:
        parts = [f"{h}: {v}" for h, v in zip(header, row) if v]
        texts.append("\n".join(parts))

    return texts


def paragraph_features(path: str) -> list[dict]:
    doc = Document(path)
    results = []

    for block in _iter_block_items(doc):
        if isinstance(block, Table):
            for row_text in _table_rows_text(block):
                results.append({
                    "text": row_text,
                    "style": "Table",
                    "bold": False,
                    "color": None,
                })
            continue

        para = block
        text = para.text.strip()
        text = re.sub(r'\n+', '\n', text)

        if not text:
            continue

        style = para.style.name

        runs = [r for r in para.runs if r.text.strip()]

        bold = bool(runs) and all(bool(r.bold) for r in runs)

        color = None
        for r in runs:
            try:
                if r.font.color.rgb is not None:
                    color = str(r.font.color.rgb)
                    break
            except AttributeError:
                pass

        results.append({
            "text": text,
            "style": style,
            "bold": bold,
            "color": color,
        })

    return results


if __name__ == "__main__":
    sample = "word_files/heading_already_files/ONE STORY, MANY CUE CARDS.docx"

    paras = paragraph_features(sample)
    print(f"Including {len(paras)} paragraphs\n")

    for p in paras[:20]:
        print(f"[{p['style']}] bold={p['bold']} color={p['color']} ")
        print(f"   {p['text'][:80]}")
        print()
