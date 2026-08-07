import os
from db.session import SessionLocal, check_connection
from db.models import Chunk
from ingestion.chunker import chunk_paragraphs
from ingestion.embedder import embed_chunks

SOURCE_DIR = "word_files/heading_already_files"


def ingest_file(session, path: str):
    chunks = chunk_paragraphs(path)
    if not chunks:
        print(f"WARNING: no chunks produced for {path}")
        return
    chunks = embed_chunks(chunks)

    session.query(Chunk).filter(
        Chunk.source_file == path, Chunk.is_active.is_(True)
    ).update({Chunk.is_active: False})

    db_chunks = []
    for chunk in chunks:
        db_chunk = Chunk(
            source_file=path,
            section_title=chunk["section_title"],
            chunk_index=chunk["chunk_index"],
            text=chunk["text"],
            embedding=chunk["embedding"],
        )
        db_chunks.append(db_chunk)
    session.add_all(db_chunks)
    session.commit()


def main():
    session = SessionLocal()
    check_connection()
    for filename in os.listdir(SOURCE_DIR):
        if filename.endswith(".docx"):
            path = os.path.join(SOURCE_DIR, filename)
            print(f"Ingesting {filename}...")
            ingest_file(session, path)
    session.close()


if __name__ == "__main__":
    main()
