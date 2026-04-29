"""Agentic RAG tool — search_knowledge_base as an Agent-callable tool with hybrid search."""

import json
import os
from pathlib import Path

from langchain.tools import tool
from langchain_milvus import Milvus

from app.config import settings

_vector_store: Milvus = None
_hybrid_retriever = None


def set_rag_vector_store(store: Milvus):
    global _vector_store
    _vector_store = store


def init_hybrid_retriever(store: Milvus = None, docs_dir: str = "aiops-docs"):
    """Initialize hybrid retriever with BM25 index from local documents."""
    global _hybrid_retriever
    vs = store or _vector_store
    if vs is None:
        return

    docs = []
    docs_path = Path(docs_dir)
    if docs_path.is_dir():
        for md_file in sorted(docs_path.glob("*.md")):
            docs.append(md_file.read_text(encoding="utf-8"))

    if docs:
        from app.rag.hybrid_search import HybridRetriever
        _hybrid_retriever = HybridRetriever(vs, docs)


@tool
def search_knowledge_base(query: str, top_k: int = None) -> str:
    """
    搜索内部运维知识库。
    当需要查询技术文档、运维手册、故障处理方案、配置说明时使用此工具。
    参数:
    - query: 搜索查询，用自然语言描述需要查找的内容
    - top_k: 返回文档数量，默认使用系统配置
    """
    if _vector_store is None:
        return json.dumps({"status": "error", "message": "知识库未初始化"}, ensure_ascii=False)

    k = top_k or settings.rag_top_k

    # Hybrid search if available (BM25 + vector → RRF)
    if _hybrid_retriever is not None:
        try:
            hybrid_results = _hybrid_retriever.retrieve(query, top_k=k)
            if hybrid_results:
                return json.dumps(hybrid_results, ensure_ascii=False, indent=2)
        except Exception:
            pass  # Fall through to pure vector search

    # Pure vector search fallback
    retriever = _vector_store.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(query)

    if not docs:
        return json.dumps({"status": "no_results", "message": "未找到相关文档"}, ensure_ascii=False)

    results = []
    for d in docs:
        cluster = d.metadata.get("_cluster", "")
        source = d.metadata.get("title") or d.metadata.get("_file_name", "unknown")
        if cluster and cluster != "default":
            source = f"[{cluster}] {source}"
        results.append({
            "content": d.page_content,
            "source": source,
            "score": d.metadata.get("score", 0.0),
        })

    return json.dumps(results, ensure_ascii=False, indent=2)
