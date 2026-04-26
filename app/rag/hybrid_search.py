"""Hybrid retriever: BM25 keyword + Milvus vector → RRF fusion."""

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer for BM25."""
    return text.lower().split()


class HybridRetriever:
    """BM25 keyword search + Milvus vector search → Reciprocal Rank Fusion.

    Usage:
        docs = ["doc1 content", "doc2 content", ...]
        retriever = HybridRetriever(vector_store, docs)
        results = retriever.retrieve("query", top_k=5)
    """

    def __init__(self, vector_store, documents: list[str]):
        self.vector_store = vector_store
        self.documents = documents
        self._bm25 = BM25Okapi([_tokenize(d) for d in documents]) if documents else None

    def _bm25_search(self, query: str, top_n: int = 20) -> list[tuple[int, float]]:
        if not self._bm25:
            return []
        tokenized = _tokenize(query)
        scores = self._bm25.get_scores(tokenized)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(idx, score) for idx, score in ranked[:top_n] if score > 0]

    def _vector_search(self, query: str, top_n: int = 20) -> list[tuple[int, float]]:
        retriever = self.vector_store.as_retriever(search_kwargs={"k": top_n})
        docs = retriever.invoke(query)
        results = []
        for i, doc in enumerate(docs):
            score = doc.metadata.get("score", 0.0)
            # Find index in original documents
            content = doc.page_content
            try:
                idx = self.documents.index(content)
            except ValueError:
                idx = i  # fallback
            results.append((idx, score))
        return results

    def _rrf_fusion(
        self,
        bm25_ranked: list[tuple[int, float]],
        vector_ranked: list[tuple[int, float]],
        k: int = 60,
    ) -> list[tuple[int, float]]:
        """Reciprocal Rank Fusion."""
        scores: dict[int, float] = {}
        for rank, (idx, _) in enumerate(bm25_ranked):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)
        for rank, (idx, _) in enumerate(vector_ranked):
            scores[idx] = scores.get(idx, 0) + 1.0 / (k + rank + 1)

        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """Retrieve documents using hybrid search.

        Returns list of dicts with: content, source, bm25_score, vector_score, fused_score
        """
        bm25_ranked = self._bm25_search(query, top_n=20)
        vector_ranked = self._vector_search(query, top_n=20)

        fused = self._rrf_fusion(bm25_ranked, vector_ranked)
        top_indices = fused[:top_k]

        bm25_map = {idx: score for idx, score in bm25_ranked}
        vec_map = {idx: score for idx, score in vector_ranked}

        results = []
        for idx, fused_score in top_indices:
            doc = self.documents[idx] if idx < len(self.documents) else ""
            results.append({
                "content": doc,
                "source": f"doc-{idx}",
                "bm25_score": bm25_map.get(idx, 0.0),
                "vector_score": vec_map.get(idx, 0.0),
                "fused_score": fused_score,
            })

        return results
