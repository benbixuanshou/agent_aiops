# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
make init              # one-click: docker compose up --build → wait → health check
make down / restart    # stop / restart all services
make logs              # tail app logs
make status / check    # container status / health check
make reindex           # re-upload aiops-docs/ to vector DB
make clean             # remove temp files & stale artifacts
make help              # list all available make targets

docker compose up -d --build   # alternative to make init
poetry run uvicorn app.main:app --host 0.0.0.0 --port 9900  # dev (no Docker)

poetry run pytest tests/test_core.py -v   # 10 core tests
poetry run python tests/eval/evaluator.py # RAG recall/MRR eval

find app tests -name "*.py" -exec python -c "import ast; ast.parse(open('{}').read())" \;
```

## Prerequisites

- Docker (app + Milvus + MySQL + Redis + Prometheus + Alertmanager run in containers)
- `.env` with `DEEPSEEK_API_KEY` (chat LLM) and `DASHSCOPE_API_KEY` (embeddings)
- Prometheus Mock mode is default (`PROMETHEUS_MOCK_ENABLED=true`)
- For local dev: Python 3.11+, Poetry

## Architecture

**Supervisor + 2 Workers multi-agent, all Docker-contained.**

```
POST /api/chat ──→ IntentGateway ──→ Supervisor ──→ RAG Agent (tech Q&A, 2 tools)
                                                    SRE Agent (incident response, 5 tools)
                        ↓
              Zero-keyword queries blocked at gateway (0 LLM cost)
              SRE Agent streamed as SSE with tool-call progress
              Context auto-compressed after 6 message pairs
```

### Three Agents

| | Supervisor | RAG Agent | SRE Agent |
|---|---|---|---|
| File | `agent/supervisor.py` | `agent/react_agent.py` | `agent/react_agent.py` |
| LLM | DeepSeek T=0.01 | DeepSeek T=0.7 | DeepSeek T=0.3 |
| Tools | 0 (routing only) | `search_knowledge_base`, `get_current_datetime` | above + `query_prometheus_alerts`, `query_logs`, `get_available_log_topics` |
| Skills | — | usually none | `log-analyzer`, `alert-triage` matched & injected |

### Key Components

- **IntentGateway** (`rag/intent.py`): Rule-based keyword(0.6)+pattern(0.4), blocks queries with zero keyword matches. Threshold 0.05. 15 troubleshooting keywords.
- **HybridRetriever** (`rag/hybrid_search.py`): BM25 (rank-bm25) + Milvus COSINE → RRF fusion. Wired into `rag_tool.py`.
- **SessionStore** (`session/manager.py`): MySQL (Docker) / SQLite (dev) backends. Redis for tool cache (hot path, 5min TTL). Auto-compresses old conversations to summaries via LLM after 6 pairs. 7-day TTL cleanup.
- **SkillLoader** (`skills/loader.py`): Scans `.claude/skills/*/SKILL.md`, matches by keyword overlap, injects into SRE Agent system prompt. 8 skills installed (5 ops + 3 garden-skills).
- **Task Templates** (`agent/task_templates.py`): 4 pre-built prompts (CPU/memory/slow/service-down). Exposed at `/api/ai_ops/templates`, frontend buttons at top-right.
- **Logging**: Python `logging` module, format: `YYYY-MM-DD HH:MM:SS [LEVEL] superbizagent: message`.

### Tools

| Tool | File | Mode |
|------|------|------|
| `search_knowledge_base` | `rag/rag_tool.py` | Hybrid (BM25 + Milvus COSINE) |
| `query_prometheus_alerts` | `tools/prometheus_tool.py` | Mock(default) / Real(httpx to Prometheus API) |
| `query_logs` | `tools/cls_logs_tool.py` | Mock (4 topics: system-metrics, app-logs, db-slow-query, system-events) |
| `get_available_log_topics` | `tools/cls_logs_tool.py` | Mock |
| `get_current_datetime` | `tools/datetime_tool.py` | Asia/Shanghai TZ |

### Vector Store

`rag/retrieval.py` — custom `MilvusStore` wrapping pymilvus directly (langchain-milvus 0.1.x had compatibility issues with pymilvus 2.6). Provides `as_retriever()` and `.col` (pymilvus Collection). `enable_dynamic_field=True`, COSINE metric, IVF_FLAT index, nprobe=10.

### Endpoints

```
POST /api/chat               Supervisor → Agent → answer
POST /api/chat_stream         SSE streaming variant
POST /api/ai_ops              Supervisor → SRE Agent → SSE (tools + report)
GET  /api/ai_ops/templates    List task templates
POST /api/ai_ops/template/{k} Run specific template
POST /api/upload              File → IndexingService → Milvus (207 on index fail)
GET  /milvus/health           {milvus, deepseek, vector_count, collection}
POST /api/chat/clear          Clear session
POST /api/ai_ops/webhook       Alertmanager webhook → auto SRE Agent (no-code trigger)
GET  /api/chat/session/{id}   Session info
GET  /                         Static frontend (dark mode, drag-drop, Ctrl+Enter)
```

### Config (.env / config.py)

- DeepSeek: `deepseek-chat`, base URL `https://api.deepseek.com`
- DashScope: embeddings `text-embedding-v4` (1024-dim)
- Milvus: collection `biz`, COSINE, 1024-dim, IVF_FLAT
- RAG: top-k=3, chunk 800/overlap 100
- Intent: threshold 0.05, troubleshooting keywords: 错误/异常/故障/报错/排查/CPU/内存/OOM...
- Prometheus/CLS: mock toggles (default true)
- Session: MySQL (Docker) / SQLite (dev fallback), Redis tool cache, 6 pairs, 7-day TTL

### Project Structure

```
app/
├── main.py                    # FastAPI lifespan: embed → vector → hybrid → agents → supervisor
├── config.py                  # pydantic-settings from .env
├── agent/
│   ├── supervisor.py          # Supervisor: 2-tier routing (rules + LLM), skill injection
│   ├── react_agent.py         # build_rag_agent() + build_sre_agent()
│   ├── tools.py               # gather_rag_tools() + gather_sre_tools()
│   └── task_templates.py      # 4 preset AIOps task prompts
├── rag/
│   ├── intent.py              # IntentRecognizer + IntentGateway + AgentConfig
│   ├── retrieval.py           # MilvusStore + MilvusRetriever (pymilvus direct)
│   ├── rag_tool.py            # search_knowledge_base @tool (hybrid search)
│   └── hybrid_search.py       # HybridRetriever (BM25 + vector → RRF)
├── tools/                     # datetime, prometheus (mock/real), cls_logs (mock)
├── ingestion/                 # chunker → embedder (DashScope) → indexer
├── session/manager.py         # MySQL/Redis/SQLite + asyncio.Lock + context compression
├── skills/loader.py           # .claude/skills/ loader (8 skills)
├── api/                       # chat, aiops, upload, health, session
└── models/schemas.py
tests/
├── test_core.py               # 10 core tests (intent 6 + session 3 + health 1)
├── test_intent.py             # intent classification tests
├── test_session.py            # session lifecycle tests
├── test_imports.py            # module import verification
└── eval/                      # 10 annotated queries + evaluator (Recall@5, MRR)
.claude/skills/                # 8 skills: alert-triage, log-analyzer, report-writer, sql-tuning,
                              #   capacity-planning, rag-skill, gpt-image-2, web-design-engineer
```

### Target Architecture (v2.0 Roadmap)

Goal: Split monolithic SRE Agent into Supervisor + 5 domain Agents to avoid tool overload:

```
Supervisor ──→ RAG Agent ────── (tech Q&A, 2 tools)
           ├─→ SRE Agent ────── (alert triage, 5 tools)
           ├─→ Platform Agent ── (K8s/DB/infra, 6-8 tools)
           ├─→ Patrol Agent ─── (scheduled health checks)
           ├─→ Action Agent ─── (controlled auto-remediation, human-confirmed)
           └─→ Notify Agent ─── (DingTalk/WeCom push)
```

**Roadmap phases** (see ARCHITECTURE.md for details):
- **P0** (next — starting now): API auth, rate limiting, error handling, logging, CI/CD
- **P1**: IM notify, alert aggregation, K8s Events, knowledge deposition, scheduled patrol
- **P2**: Integration tests 70%+, Alembic migrations, multi-env config, change correlation
- **P3**: Multi-tenancy, audit, ITSM, SLO, War Room, Runbook engine, plugin marketplace

### Key Decisions

- **No langchain-milvus** — replaced with custom pymilvus wrapper (MilvusStore) due to hang on constructor.
- **No `enable_dynamic_field=False`** — old `metadata_field` approach deprecated, dynamic fields used throughout.
- **LLM is DeepSeek** via `langchain-openai.ChatOpenAI` with `base_url`. Embeddings still DashScope.
- **No RAGPipeline** — chat always goes through Supervisor → Agent.
- **IntentGateway blocks zero-score only** — single keyword match passes through.
- **Prometheus Mock is default**— real Prometheus available in docker-compose.
- **Skills are `.claude/skills/<name>/SKILL.md` files** — progressive disclosure, keyword-matched and injected into system prompt.
