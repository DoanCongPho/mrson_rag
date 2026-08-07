import os
import unicodedata
from db.session import SessionLocal, check_connection
from db.models import Chunk, Document
from ingestion.chunker import chunk_paragraphs
from ingestion.embedder import embed_chunks
from ingestion.tracing import tracer_provider
from openinference.semconv.trace import SpanAttributes

SOURCE_DIR = "word_files/heading_already_files"


tracer = tracer_provider.get_tracer(__name__)


def ingest_file(session, path: str, filename: str):

    with tracer.start_as_current_span(f"ingest: {filename}") as file_span:
        file_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
        file_span.set_attribute(SpanAttributes.INPUT_VALUE, path)

        normalized_filename = unicodedata.normalize("NFC", filename)
        doc = session.query(Document).filter(Document.name == normalized_filename).first()
        if doc is None:
            print(f"WARNING: no Document record for {normalized_filename} (run update_docs sync first, or filename differs from Drive), doc_url will be empty")

        with tracer.start_as_current_span("chunk") as chunk_span:
            chunk_span.set_attribute(SpanAttributes.OPENINFERENCE_SPAN_KIND, "CHAIN")
            chunk_span.set_attribute(SpanAttributes.INPUT_VALUE, path)
            chunks = chunk_paragraphs(path)
            chunk_span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(chunks)} chunks")

        if not chunks:
            print(f"WARNING: no chunks produced for {path}")
            return
        chunks = embed_chunks(chunks)
        file_span.set_attribute(SpanAttributes.OUTPUT_VALUE, f"{len(chunks)} chunks embedded")

        session.query(Chunk).filter(
            Chunk.source_file == path, Chunk.is_active.is_(True)
        ).update({Chunk.is_active: False})

        db_chunks = []
        for chunk in chunks:
            db_chunk = Chunk(
                doc_url=doc.url if doc else None,
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
            ingest_file(session, path, filename)
    session.close()


if __name__ == "__main__":
    main()
