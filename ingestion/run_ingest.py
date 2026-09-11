import os
import unicodedata
from db.session import SessionLocal, check_connection
from db.models import Chunk, Document
from ingestion.chunker import chunk_paragraphs
from ingestion.embedder import embed_chunks
from ingestion.tracing import tracer_provider
from openinference.semconv.trace import SpanAttributes
from ingestion.cleanup_chunks import clean

SOURCE_DIR = "word_files/heading_already_files"
INGESTED_DIR = os.path.join(SOURCE_DIR, "ingested")
UNINGESTED_DIR = os.path.join(SOURCE_DIR, "un-ingested")
CATEGORIES = ["part2", "part3", "writing"]


tracer = tracer_provider.get_tracer(__name__)


def ingest_file(session, disk_path: str, logical_source_file: str, filename: str, category: str):

    with tracer.start_as_current_span(f"ingest: {filename}") as span:
        span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        span.set_attribute(SpanAttributes.INPUT_VALUE, disk_path)

        normalized_filename = unicodedata.normalize("NFC", filename)
        doc = session.query(Document).filter(Document.name == normalized_filename).first()
        if doc is None:
            print(f"WARNING: no Document record for {normalized_filename} (run update_docs sync first, or filename differs from Drive), doc_url will be empty")

        with tracer.start_as_current_span("chunk") as chunk_span:
            chunk_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            chunk_span.set_attribute(SpanAttributes.INPUT_VALUE, disk_path)
            chunks = chunk_paragraphs(disk_path)
            chunk_span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(chunks)} chunks")

        if not chunks:
            print(f"WARNING: no chunks produced for {disk_path}")
            return
        chunks = embed_chunks(chunks)
        span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(chunks)} chunks embedded")

        session.query(Chunk).filter(
            Chunk.source_file == logical_source_file, Chunk.is_active.is_(True)
        ).update({Chunk.is_active: False})

        # Clean redundant chunks before running ingest.
        clean(session)

        db_chunks = []
        for chunk in chunks:
            db_chunk = Chunk(
                doc_url=doc.url if doc else None,
                source_file=logical_source_file,
                section_title=chunk["section_title"],
                chunk_index=chunk["chunk_index"],
                text=chunk["text"],
                embedding=chunk["embedding"],
                category=category,
            )
            db_chunks.append(db_chunk)
        session.add_all(db_chunks)
        session.commit()

        ingested_path = os.path.join(INGESTED_DIR, category, filename)
        os.replace(disk_path, ingested_path)


def main():
    session = SessionLocal()
    check_connection()
    for category in CATEGORIES:
        category_dir = os.path.join(UNINGESTED_DIR, category)
        for filename in os.listdir(category_dir):
            if filename.endswith(".docx"):
                disk_path = os.path.join(category_dir, filename)
                logical_source_file = os.path.join(SOURCE_DIR, category, filename)
                print(f"Ingesting [{category}] {filename}...")
                ingest_file(session, disk_path, logical_source_file, filename, category)
    session.close()


if __name__ == "__main__":
    main()
