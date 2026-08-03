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

def retrieve(query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
    query_vector = embed_query(query)
    session = SessionLocal()
    distance = Chunk.embedding.cosine_distance(query_vector)
    results = (
        session.query(Chunk, distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
        .all()
    )
    session.close()
    return [(chunk, float(dist)) for chunk, dist in results]


def main():
    query = "Value line là gì?"
    results = retrieve(query)
    for chunk, distance in results:
        print(f"{chunk.section_title} (distance={distance:.4f})")
    print()

if __name__ == "__main__":
    main()