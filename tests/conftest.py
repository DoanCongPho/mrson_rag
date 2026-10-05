import os

# Keep tests offline and fast: no Phoenix exporter, no reranker model load.
os.environ.setdefault("PHOENIX_ENABLED", "false")
os.environ.setdefault("RERANKER_ENABLED", "false")
