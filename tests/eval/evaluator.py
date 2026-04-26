"""RAG evaluation — recall@K and MRR on 10 annotated queries."""

import json
from pathlib import Path


def evaluate(retriever, queries_path: str = None) -> dict:
    if queries_path is None:
        queries_path = Path(__file__).parent / "queries.json"
    with open(queries_path) as f:
        queries = json.load(f)

    recalls, mrrs = [], []
    for q in queries:
        results = retriever.invoke(q["query"])
        sources = {get_source(r) for r in results}
        relevant = set(q["relevant"])

        # Recall@K
        hits = sources & relevant
        recalls.append(len(hits) / len(relevant) if relevant else 1.0)

        # MRR
        for i, r in enumerate(results):
            if get_source(r) in relevant:
                mrrs.append(1.0 / (i + 1))
                break
        else:
            mrrs.append(0.0)

    return {
        "recall@5": round(sum(recalls) / len(recalls), 3),
        "mrr": round(sum(mrrs) / len(mrrs), 3),
        "queries": len(queries),
    }


def get_source(doc) -> str:
    if hasattr(doc, "metadata"):
        fn = doc.metadata.get("_file_name", "")
        return fn.split("/")[-1]
    if isinstance(doc, dict):
        fn = doc.get("_file_name", doc.get("source", ""))
        return fn.split("/")[-1]
    return str(doc)


if __name__ == "__main__":
    # Quick manual test: load vector store and run eval
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from app.rag.retrieval import init_vector_store
    from app.ingestion.embedder import init_embedding_service

    embedder = init_embedding_service()
    vs = init_vector_store(embedder)
    retriever = vs.as_retriever(search_kwargs={"k": 5})

    result = evaluate(retriever)
    print(f"Recall@5: {result['recall@5']}, MRR: {result['mrr']}")
