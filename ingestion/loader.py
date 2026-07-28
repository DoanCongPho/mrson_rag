from docx import Document



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


