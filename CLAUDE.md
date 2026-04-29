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

poetry run pytest tests/ -v    # all tests
poetry run python tests/eval/evaluator.py # RAG recall/MRR eval
```

## Prerequisites

- Docker (9 containers: app + Milvus + etcd + minio + Attu + MySQL + Redis + Prometheus + Alertmanager)
- `.env` with `DEEPSEEK_API_KEY` and `DASHSCOPE_API_KEY`
- Mock mode is default (`PROMETHEUS_MOCK_ENABLED=true`, `CLS_MOCK_ENABLED=true`, `K8S_MOCK_ENABLED=true`)
- For local dev: Python 3.11+, Poetry

## Architecture

**Supervisor + 2 Workers, all Docker-contained.**

```
POST /api/chat ──→ IntentGateway(2层) ──→ Supervisor ──→ RAG Agent(3 tools)
                                                    SRE Agent(17 tools)
                        ↓
              Layer1: ~100-word relevance check → 0 hits + <6 chars → block
              Layer2: intent score >0.05 → strong(internal KB first), ≤0.05 → weak(web directly)
              SRE Agent streamed as SSE with tool-call progress
              Context auto-compressed after 6 message pairs
```

### Core Agents (3 ReAct + 4 supporting = 7 total)

| | Supervisor | RAG Agent | SRE Agent |
|---|---|---|---|
| File | `agent/supervisor.py` | `agent/react_agent.py` | `agent/react_agent.py` |
| LLM | DeepSeek T=0.01 | DeepSeek T=0.7 | DeepSeek T=0.3 |
| Tools | 0 | `search_knowledge_base`, `get_current_datetime`, `web_search` | above + `query_prometheus_alerts`, `query_logs`, `query_k8s_events`, `query_recent_deployments`, `query_slo_status` |
| Skills | — | — | `log-analyzer`, `alert-triage` |

### Key Components

- **IntentGateway** (`rag/intent.py`): Two-layer design. Layer1: ~100 generic tech keywords + 6-char fallback → block truly irrelevant queries. Layer2: per-category keywords(60%) + patterns(40%) → intent score → strong(>0.05, internal KB first) / weak(≤0.05, web directly).
- **HybridRetriever** (`rag/hybrid_search.py`): BM25 (rank-bm25) + Milvus COSINE → RRF fusion.
- **SessionStore** (`session/manager.py`): MySQL/SQLite backends with asyncio.Lock. Redis tool cache (5min TTL). Auto-compresses old conversations after 6 pairs. 7-day TTL. MySQL pool_recycle=3600, SQLite WAL mode.
- **SkillLoader** (`skills/loader.py`): Scans `.claude/skills/*/SKILL.md`, keyword-matched and injected into SRE Agent system prompt. 7 active skills.
- **Tenant store** (`tenant_store.py`): API Key → Tenant + Role mapping. Configured via `.claude/tenants.json`.
- **Self monitor** (`self_monitor.py`): Agent health metrics (LLM success rate, latency, alert storm detection).
- **Middleware** (pure ASGI): ApiKeyMiddleware, RateLimitMiddleware, LoggingMiddleware. All avoid BaseHTTPMiddleware ExceptionGroup issues.

### Tools (17 total — 10 shared + 7 SRE-only)

| Tool | File | Mode |
|------|------|------|
| `search_knowledge_base` | `rag/rag_tool.py` | Hybrid (BM25 + Milvus COSINE) |
| `web_search` | `tools/web_search_tool.py` | DuckDuckGo (free) |
| `get_current_datetime` | `tools/datetime_tool.py` | Asia/Shanghai TZ |
| `query_prometheus_alerts` | `tools/prometheus_tool.py` | Real (httpx) / Mock |
| `query_logs` | `tools/cls_logs_tool.py` | Real (ES/Loki) / Mock |
| `query_k8s_events` | `tools/k8s_tools.py` | Real (REST API) / Mock |
| `query_recent_deployments` | `tools/change_tools.py` | Real (GitLab API) / Mock |
| `query_slo_status` | `tools/slo_tools.py` | Real (Prometheus) / Mock |
| `query_service_topology` | `tools/topology_tools.py` | Mock (6 services) |
| `query_blast_radius` | `tools/topology_tools.py` | Mock |
| `score_service_health` | `tools/health_scorer.py` | Mock (4 services, A-D) |
| `run_compliance_check` | `tools/compliance_tools.py` | Mock (8 checks) |
| `check_cost_anomaly` | `tools/cost_tools.py` | Mock (6 services) |
| `predict_capacity` | `tools/capacity_tools.py` | Mock (4 services, 30-day) |
| `propose_action` | `agent/agents/action_agent.py` | Action Agent only |
| `get_pending_actions` | `agent/agents/action_agent.py` | Action Agent only |
| `get_available_log_topics` | `tools/cls_logs_tool.py` | Mock |
| `get_k8s_namespaces` | `tools/k8s_tools.py` | Mock |

### Endpoints

```
POST /api/chat               Supervisor → Agent → answer
POST /api/chat_stream         SSE streaming
POST /api/ai_ops              SRE Agent → SSE (tools + report)
POST /api/ai_ops/webhook       Alertmanager → auto SRE Agent
POST /api/ai_ops/template/{k} Run template (8 available, P0/P1/P2)
GET  /api/ai_ops/templates    List templates
POST /api/login                Validate API Key → tenant info
POST /api/knowledge/confirm    Confirm finding → index to Milvus
POST /api/upload               File → IndexingService → Milvus
GET  /api/admin/stats          Global stats (admin only)
GET  /api/admin/tenants        Current tenant info
GET  /milvus/health            {milvus, deepseek, vector_count, agent, cluster}
GET  /metrics                  Prometheus format
GET  /docs                     Swagger UI
POST /api/chat/clear           Clear session
GET  /api/chat/session/{id}    Session info
GET  /                          Web UI (dark ops dashboard + inline tabs)
```

### Project Structure

```
app/
├── main.py                    # FastAPI lifespan + all middleware + patrol start
├── config.py                  # pydantic-settings: DeepSeek + Milvus + MySQL + Redis
├── tenant_store.py            # API Key → Tenant + Role mapping
├── self_monitor.py            # Agent health metrics
├── agent/
│   ├── supervisor.py          # 2-tier routing (rules + LLM), skill injection
│   ├── react_agent.py         # build_rag_agent() + build_sre_agent()
│   ├── tools.py               # gather_rag_tools(3) + gather_sre_tools(9)
│   ├── task_templates.py      # 8 AIOps task prompts (P0/P1/P2)
│   ├── alert_aggregator.py    # Alert → Incident grouping
│   └── agents/
│       └── patrol_agent.py    # Scheduled health checks
├── rag/
│   ├── intent.py              # IntentRecognizer(2-layer) + IntentGateway + AgentConfig
│   ├── retrieval.py           # MilvusStore + MilvusRetriever (pymilvus)
│   ├── rag_tool.py            # search_knowledge_base @tool
│   └── hybrid_search.py       # HybridRetriever (BM25 + COSINE → RRF)
├── tools/
│   ├── datetime_tool.py       # get_current_datetime
│   ├── prometheus_tool.py     # query_prometheus_alerts (mock/real)
│   ├── cls_logs_tool.py       # query_logs + get_available_log_topics
│   ├── k8s_tools.py           # query_k8s_events + get_k8s_namespaces
│   ├── change_tools.py        # query_recent_deployments
│   ├── slo_tools.py           # query_slo_status
│   └── web_search_tool.py     # DuckDuckGo web search
├── middleware/
│   ├── auth.py                # API Key auth (pure ASGI)
│   ├── rate_limit.py          # Sliding window (Redis + memory)
│   ├── logging.py             # Structured logging + X-Request-ID
│   └── error_handler.py       # Global exception handler
├── notify/
│   └── dingtalk.py            # DingTalk group bot
├── session/manager.py         # MySQL/Redis/SQLite + context compression + tool cache
├── ingestion/                 # chunker → embedder(DashScope) → indexer
├── skills/loader.py           # .claude/skills/*/SKILL.md loader (7 skills)
├── api/
│   ├── chat.py                # Chat + chat_stream
│   ├── aiops.py               # AIOps + webhook + templates
│   ├── admin.py               # Login + admin stats + tenant info
│   ├── knowledge.py           # Knowledge confirm (RBAC)
│   ├── metrics.py             # Prometheus /metrics
│   ├── upload.py              # File upload
│   ├── health.py              # /milvus/health
│   └── session.py             # Session clear + info
└── models/schemas.py          # Pydantic v2 request/response models

tests/
├── conftest.py                # Shared fixtures (mock_alerts)
├── test_core.py               # Intent + session + health (10 tests)
├── test_intent.py             # Intent classification (6 tests)
├── test_session.py            # Session lifecycle (5 tests)
├── test_imports.py            # Import verification (7 tests)
├── agent/test_aggregator.py   # Alert aggregator (6 tests)
├── api/test_endpoints.py      # HTTP endpoints (6 tests)
├── tools/test_tools.py        # Tool mock data (9 tests)
└── eval/                      # RAG evaluation (10 queries, Recall@5=1.0)

.claude/
├── skills/                    # 7 skills (5 ops + 2 garden)
├── tenants.json               # Multi-tenant config
└── settings.json              # Plugin config
```

### Routes & Roadmap

- **P0** (done): API auth, rate limiting, error handling, logging, CI/CD, Docker hardening
- **P1** (done): IM notify, alert aggregation, K8s Events, patrol, graded runbooks, knowledge deposition
- **P2** (done): Integration tests, Alembic migrations, multi-env, change correlation, connection pool fix
- **P3** (done): Multi-tenant + RBAC, SLO, self-monitoring, web search, 2-layer intent routing

### Key Decisions

- **No langchain-milvus** — custom pymilvus wrapper (MilvusStore) due to hang on constructor.
- **LLM is DeepSeek** via `langchain-openai.ChatOpenAI`. Embeddings still DashScope.
- **2-layer intent routing** — relevance keywords filter garbage, intent score decides internal-KB-first vs web-direct.
- **Pure ASGI middleware** — avoids Starlette BaseHTTPMiddleware ExceptionGroup issues.
- **Prometheus/CLS/K8s Mock default** — toggle to real in prod via env vars.
- **Skills are `.claude/skills/<name>/SKILL.md`** — progressive disclosure, keyword-matched, injected into system prompt.
- **No automatic git push** — commits are manual, push on explicit request only.
