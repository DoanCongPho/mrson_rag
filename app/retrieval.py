from openai import OpenAI
from config import settings
from db.session import SessionLocal
from db.models import Chunk

client = OpenAI(api_key=settings.openai_api_key)

def embed_query(query: str) -> list[float]:
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=query,
    )
    return response.data[0].embedding

def retrieve(query: str, top_k: int = 5) -> list[Chunk]:
    query_vector = embed_query(query)
    session = SessionLocal()
    results = (
        session.query(Chunk)
        .order_by(Chunk.embedding.cosine_distance(query_vector))
        .limit(top_k)
        .all()
    )
    session.close()
    return results


def main():
    query = "Value line là gì?"
    chunks = retrieve(query)
    for c in chunks:
        print(c.section_title)
    print()

if __name__ == "__main__":
    main()