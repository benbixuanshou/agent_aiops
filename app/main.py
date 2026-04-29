import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings


def _setup_logging():
    if settings.app_env == "dev":
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
            '"msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        ))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.handlers = [handler]

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "pymilvus", "aiomysql"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_setup_logging()
logger = logging.getLogger("superbizagent")


async def _ensure_docs_indexed(vector_store, embedder):
    """Auto-ingest aiops-docs/ on first run if Milvus collection is empty."""
    try:
        if vector_store.col.num_entities > 0:
            return
    except Exception:
        logger.warning("auto_ingestion: could not check vector count, skipping")

    docs_dir = Path("aiops-docs")
    if not docs_dir.is_dir():
        return

    from app.ingestion.indexer import IndexingService
    indexer = IndexingService(vector_store, embedder)
    for md_file in sorted(docs_dir.glob("*.md")):
        try:
            await indexer.index_file(str(md_file))
        except Exception:
            logger.warning("auto_ingestion: failed to index %s", md_file.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from app.rag.retrieval import init_vector_store
    from app.ingestion.embedder import init_embedding_service

    logger.info("Starting SuperBizAgent...")
    embedder = init_embedding_service()
    logger.info("Embedding service ready")
    vector_store = init_vector_store(embedder)
    logger.info(f"Milvus connected, collection: {settings.milvus_collection}")
    app.state.embedder = embedder
    app.state.vector_store = vector_store

    # Inject vector store into the RAG tool + init hybrid search
    from app.rag.rag_tool import set_rag_vector_store, init_hybrid_retriever
    set_rag_vector_store(vector_store)
    init_hybrid_retriever(vector_store)

    # Auto-ingest on first run (background, don't block startup)
    import asyncio as _asyncio
    _asyncio.create_task(_ensure_docs_indexed(vector_store, embedder))

    from app.agent.react_agent import build_rag_agent, build_sre_agent
    from app.agent.tools import gather_rag_tools, gather_sre_tools
    from langchain_openai import ChatOpenAI

    # RAG Agent — 技术问答 (T=0.7, 2 tools)
    rag_llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=settings.deepseek_temperature,
        max_tokens=settings.deepseek_max_tokens,
    )
    app.state.rag_agent = build_rag_agent(rag_llm, gather_rag_tools())

    # SRE Agent — 告警排查 (T=0.3, 5 tools)
    sre_llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.3,
        max_tokens=8000,
    )
    app.state.sre_agent = build_sre_agent(sre_llm, gather_sre_tools())

    # Supervisor — routes between RAG Agent and SRE Agent
    from app.agent.supervisor import Supervisor
    supervisor_llm = ChatOpenAI(
        model=settings.deepseek_model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.01,
        max_tokens=200,
    )
    app.state.supervisor = Supervisor(
        llm=supervisor_llm,
        rag_agent=app.state.rag_agent,
        sre_agent=app.state.sre_agent,
    )
    logger.info("Supervisor + 2 Agents ready (RAG + SRE)")

    # Patrol agent — scheduled health checks
    from app.agent.agents.patrol_agent import PatrolAgent
    from app.tools.prometheus_tool import query_prometheus_alerts as patrol_prom
    from app.tools.k8s_tools import query_k8s_events as patrol_k8s
    patrol = PatrolAgent(tools={
        "query_prometheus_alerts": patrol_prom,
        "query_k8s_events": patrol_k8s,
    })
    app.state.patrol = patrol
    import asyncio as _asyncio2
    _asyncio2.create_task(patrol.start())
    logger.info("Patrol agent started (interval=%s min)", settings.patrol_interval_minutes)

    yield

    # Shutdown
    try:
        vector_store.close()
    except Exception:
        logger.warning("shutdown: vector_store.close() failed")


app = FastAPI(title="SuperBizAgent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# P0 middleware (ordered: outermost first)
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.auth import ApiKeyMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ApiKeyMiddleware)
app.add_middleware(RateLimitMiddleware)

# Import and include routers
from app.api import chat, aiops, upload, health, session, knowledge, metrics
app.include_router(chat.router, prefix="/api")
app.include_router(aiops.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(health.router)
app.include_router(session.router, prefix="/api/chat")
app.include_router(knowledge.router, prefix="/api")
app.include_router(metrics.router, prefix="")

# Mount static files for the web UI (after API routes)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
