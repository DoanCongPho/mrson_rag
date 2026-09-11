# Evaluation method
    Key metrics
    Track latency, thoughput, memory, and compute usage
    Quality metrics
    Human feedback
    A/B testing
    detailed text feedback
    Pre-compiled test datasets
    Manual quality assessments
    LLM as a Judge
    RAGAS


# SEARCHING
    HYBRID SEARCH ()


# VECTOR DATABASE
    Changing to vector database and real production retrieve algorithm (HNSM - Hireachical Navigable Small Word)
# CHUNKING
    Change the chunking strategy --> parent-child chunking.
    Contextual retrieval.

# Quantization (Should we apply or not)


# Authentication system.




# Query Reformulation
    HyDE
    Query rewriting truoc retrieval: khi query gom ca doan van dai can phan tich
    ("...cau nay..., xac dinh keyword trong cau nay") + cau lenh that su, ca
    bi-encoder (cosine) lan cross-encoder (rerank) deu embed/so sanh nguyen
    chuoi -> doan van vi du (khong lien quan corpus) lam loang tin hieu cua
    cau lenh that -> rerank score gan 0 cho MOI candidate (khac voi truong hop
    match tot, score thuong 0.4-0.9), chunk dung van co trong shortlist 30
    nhung khong duoc xep hang cao. Fix: 1 LLM call nho (kieu router) tach cau
    lenh ra khoi doan van vi du, chi embed phan cau lenh de retrieve; doan
    van van duoc giu nguyen de dua vao prompt cho LLM generation.


# Reranking (done -- AITeamVN/Vietnamese_Reranker, xem app/reranker.py)


# TERMINOLOGIES NEED TO LEARN:
    HyDE
    HYBRID SEARCH



RAG eval:

Retrieve phase:
Precision
Recall
Hit rate
Mean Reciprocal Rank
Normalized Discounted Cumulative Gain

Generative phase:
Faithfulness
Answer Relevancy
Answer Correctness

