from openai import OpenAI
from config import settings



client  = OpenAI(api_key=settings.openai_api_key)



def embed_chunks(chunks: list[dict]) -> list[dict]:

    repsponse = client.embeddings.create(
        model="text-embedding-3-small",
        input=[c["text"] for c in chunks],
    )
    for chunk, item in zip(chunks, repsponse.data):
        chunk["embedding"] = item.embedding
    return chunks



if __name__ == "__main__":
    from ingestion.chunker import chunk_paragraphs

    chunks = chunk_paragraphs("word_files/heading_already_files/ONE STORY, MANY CUE CARDS.docx")
    chunks = embed_chunks(chunks)

    for c in chunks[:3]:
        print(f"[{c['section_title']}] chunk_index={c['chunk_index']} embedding_dim={len(c['embedding'])}")
        print(f"   first 5 values: {c['embedding'][:5]}")
        print()