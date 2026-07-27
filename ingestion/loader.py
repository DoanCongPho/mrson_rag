from docx import Document

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def paragraph_features(path: str) -> list[dict]:

    doc = Document(path)
    results = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        style = para.style.name

        runs = [r for r in para.runs if r.text.strip()]

        bold = bool(runs) and all(bool(r.bold) for r in runs)

        color = None
        for r in runs:
            if r.font.color is not None and r.font.color.rgb is not None:
                color = str(r.font.color.rgb)
                break

        shading = None
        shd = para._p.find(f".//{W_NS}shd")
        if shd is not None:
            fill = shd.get(f"{W_NS}fill")
            if fill and fill != "auto":
                shading = fill

        results.append({
            "text": text,
            "style": style,
            "bold": bold,
            "color": color,
            "shading": shading,
        })

    return results


if __name__ == "__main__":
    sample = "word_files/heading_already_files/ONE STORY, MANY CUE CARDS.docx"

    paras = paragraph_features(sample)
    print(f"Including {len(paras)} paragraphs\n")

    for p in paras[:20]:
        print(f"[{p['style']}] bold={p['bold']} color={p['color']} "
              f"shading={p['shading']}")
        print(f"   {p['text'][:80]}")
        print()


