# SuperBizAgent 架构

> 最后更新: 2026-04-29 | 版本: v2.0 | 状态: 内部可用

---

## 全景

```
                          POST /api/chat {Id, Question}
                                     │
                                     ▼
                          ┌──────────────────────────┐
                          │   IntentGateway (2层)     │  app/rag/intent.py
                          │                          │
                          │  Layer1: 相关性(~100词)    │
                          │    0 hits + <6 chars      │→ block (0 LLM cost)
                          │    ≥1 hit or ≥6 chars     │→ pass
                          │                          │
                          │  Layer2: 意图分类          │
                          │    keyword(60%)+pattern(40%)│
                          │    score > 0.05 → strong   │
                          │    score ≤ 0.05 → weak     │
                          └────────────┬─────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────┐
                        │   Supervisor Agent        │  app/agent/supervisor.py
                        │                          │
                        │  2-tier routing:          │
                        │  Fast: IntentGateway      │
                        │  Slow: LLM (T=0.01,200tk) │
                        │                          │
                        │  TROUBLESHOOTING → sre    │
                        │  TECH/CONFIG     → rag    │
                        │  weak_relevance   → rag   │
                        │                          │
                        │  + Skills injection       │
                        │  + Intent context hints    │
                        └──────┬──────────┬────────┘
                               │          │
                   ┌───────────┘          └───────────┐
                   ▼                                   ▼
    ┌──────────────────────────┐      ┌──────────────────────────┐
    │   RAG Agent               │      │   SRE Agent               │
    │   react_agent.py          │      │   react_agent.py          │
    │                          │      │                          │
    │ LLM: DeepSeek            │      │ LLM: DeepSeek            │
    │      T=0.7, 2000tk       │      │      T=0.3, 8000tk       │
    │                          │      │                          │
    │ Tools (3):               │      │ Tools (9):               │
    │  search_knowledge_base   │      │  search_knowledge_base   │
    │  web_search (DuckDuckGo) │      │  web_search              │
    │  get_current_datetime    │      │  get_current_datetime    │
    │                          │      │  query_prometheus_alerts │
    │                          │      │  query_logs              │
    │                          │      │  query_k8s_events        │
    │                          │      │  query_recent_deployments│
    │                          │      │  query_slo_status        │
    │                          │      │                          │
    │                          │      │ Skills injected:         │
    │                          │      │  log-analyzer            │
    │                          │      │  alert-triage            │
    └──────────┬───────────────┘      └──────────┬───────────────┘
               │                                  │
               └────────────┬─────────────────────┘
                            │
               ┌────────────┴────────────────┐
               │      共享基础设施             │
               │                             │
               │ ┌─────────────────────────┐ │
               │ │ HybridRetriever         │ │  BM25 + Milvus COSINE → RRF
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ SessionStore            │ │  MySQL/Redis/SQLite
               │ │ Context compression     │ │  6轮自动 LLM 摘要
               │ │ Multi-tenant scoped     │ │  tenant_id 前缀隔离
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ SkillLoader (7 skills)  │ │  keyword-matched injection
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ AlertAggregator         │ │  5min窗口 + 标签归并
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ PatrolAgent             │ │  定时巡检 (可配置间隔)
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ Middleware Stack        │ │  Auth / RateLimit / Logging
               │ │ (pure ASGI, 4 层)        │ │  ErrorHandler / CORS
               │ └─────────────────────────┘ │
               │ ┌─────────────────────────┐ │
               │ │ Multi-Tenant (RBAC)     │ │  Admin / Operator / Viewer
               │ └─────────────────────────┘ │
               └─────────────────────────────┘
```

---

## 数据流

### /api/chat — 智能问答（三层路由）

```
ChatRequest → IntentGateway.route()
  │
  ├─ [Layer1] relevance_check(query)
  │    └─ 0 hits AND < 6 chars → block "我是运维助手…"
  │
  ├─ [Layer2] intent score (keyword 0.6 + pattern 0.4)
  │    ├─ score > 0.05 → strong_relevance
  │    │    └─ RAG Agent: search_knowledge_base → 有则回答, 无则 web_search
  │    └─ score ≤ 0.05 → weak_relevance
  │         └─ RAG Agent: 跳过 KB, 直接 web_search → 标注"来自网络搜索"
  │
  └─ Supervisor.route(): Fast(intent) + Slow(LLM) → rag / sre
       └─ _inject_context: prompt + matched skills → Agent.invoke()
```

### /api/ai_ops — 告警排查

```
POST /api/ai_ops → Supervisor.astream(SRE_TASK)
  └─ inject_context: IntentGateway prompt + matched Skills
  └─ astream loop (ReAct events)
       ├─ tool_calls → SSE: "调用工具: {name}"
       └─ ai.content → final_content → SSE 80-char chunks
  └─ save to tool cache (30-day TTL)
  └─ send dingtalk notification
```

### /api/ai_ops/webhook — Alertmanager 自动触发

```
Alertmanager → POST /api/ai_ops/webhook
  └─ HMAC-SHA256 signature verification
  └─ AlertAggregator: group alerts → incidents
  └─ Supervisor.invoke(task) → answer
  └─ cache result + dingtalk notification
```

---

## Agent 矩阵

| | Supervisor | RAG Agent | SRE Agent |
|---|---|---|---|
| 文件 | `supervisor.py` | `react_agent.py` | `react_agent.py` |
| LLM | DeepSeek T=0.01 | DeepSeek T=0.7 | DeepSeek T=0.3 |
| max_tokens | 200 | 2000 | 8000 |
| 工具数 | 0 | 3 (kb + web + dt) | 9 (kb + web + dt + prom + logs + k8s + change + slo) |
| 决策空间 | 路由 + 串行 | 检索策略 + 联网兜底 | 多工具并行排查 |

---

## 工具清单

| # | 工具 | 文件 | 模式 | Agent |
|---|------|------|------|-------|
| 1 | `search_knowledge_base` | `rag/rag_tool.py` | Hybrid (BM25+Milvus COSINE→RRF) | RAG+ SRE |
| 2 | `web_search` | `tools/web_search_tool.py` | DuckDuckGo (free, no key) | RAG+ SRE |
| 3 | `get_current_datetime` | `tools/datetime_tool.py` | Asia/Shanghai | RAG+ SRE |
| 4 | `query_prometheus_alerts` | `tools/prometheus_tool.py` | Mock / Real (httpx) | SRE |
| 5 | `query_logs` | `tools/cls_logs_tool.py` | Mock (4 topics) | SRE |
| 6 | `get_available_log_topics` | `tools/cls_logs_tool.py` | Mock | SRE |
| 7 | `query_k8s_events` | `tools/k8s_tools.py` | Mock (5 events) | SRE |
| 8 | `get_k8s_namespaces` | `tools/k8s_tools.py` | Mock | SRE |
| 9 | `query_recent_deployments` | `tools/change_tools.py` | Mock (3 deploys) | SRE |
| 10 | `query_slo_status` | `tools/slo_tools.py` | Mock (3 services) | SRE |

---

## 中间件栈（执行顺序：内→外）

```
CORS → ErrorHandler → Logging → Auth → RateLimit → Router
```

| 中间件 | 类型 | 功能 |
|---|---|---|
| CORS | Starlette | allow all origins |
| Logging | Pure ASGI | X-Request-ID + duration + status per request |
| Auth | Pure ASGI | X-API-Key → tenant context injection |
| RateLimit | Pure ASGI | Sliding window (Redis) / In-memory fallback |

---

## Skills 清单（7 个）

| Skill | 类型 | 触发场景 |
|---|---|---|
| `alert-triage` | 运维 | 多条告警同时触发，分级分类 |
| `log-analyzer` | 运维 | 错误日志、异常堆栈、故障时间线 |
| `report-writer` | 运维 | Agent 完成排查，输出最终报告 |
| `sql-tuning` | 运维 | 慢查询、连接池耗尽、查询超时 |
| `capacity-planning` | 运维 | CPU/内存持续高负载，扩容建议 |
| `rag-skill` | 通用 | PDF/Excel 文档检索 |
| `web-design-engineer` | 通用 | Web 前端可视化 |

---

## LLM & Embedding

```
Chat:     DeepSeek deepseek-chat (langchain-openai.ChatOpenAI)
Embed:    DashScope text-embedding-v4 (1024-dim)
Vector:   Milvus 2.5.10 (Docker standalone, custom pymilvus wrapper)
          COSINE, IVF_FLAT, nprobe=10, enable_dynamic_field=True
```

---

## 端点

```
POST /api/chat               Supervisor → Agent → answer
POST /api/chat_stream         SSE streaming
POST /api/ai_ops              SRE Agent → SSE (tools + report)
POST /api/ai_ops/webhook       Alertmanager → auto SRE Agent
GET  /api/ai_ops/templates    8 templates (P0/P1/P2)
POST /api/ai_ops/template/{k} Run specific template
POST /api/login                Validate API Key → tenant info
POST /api/knowledge/confirm    Confirm finding → index to Milvus (RBAC: write+)
POST /api/upload               File → chunk → embed → index
GET  /api/admin/stats          Global stats (admin only)
GET  /api/admin/tenants        Current tenant info
GET  /milvus/health            {milvus, deepseek, vector_count, agent}
GET  /metrics                  Prometheus text format
GET  /docs                     OpenAPI Swagger
POST /api/chat/clear           Clear session
GET  /api/chat/session/{id}    Session info
GET  /                          Web UI
```

---

## 文件结构

```
app/
├── main.py                    # FastAPI lifespan + middleware + patrol start
├── config.py                  # pydantic-settings (~30 fields)
├── tenant_store.py            # API Key → Tenant + Role registry
├── self_monitor.py            # Agent health metrics (LLM rate, latency, throttle)
├── agent/
│   ├── supervisor.py          # 2-tier routing + skill injection
│   ├── react_agent.py         # build_rag_agent() + build_sre_agent()
│   ├── tools.py               # gather_rag_tools(3) + gather_sre_tools(9)
│   ├── task_templates.py      # 8 AIOps prompts (P0/P1/P2)
│   ├── alert_aggregator.py    # Alert → Incident (5min window)
│   └── agents/
│       └── patrol_agent.py    # Scheduled health checks
├── rag/
│   ├── intent.py              # IntentRecognizer (2-layer) + IntentGateway
│   ├── retrieval.py           # MilvusStore (pymilvus direct)
│   ├── rag_tool.py            # search_knowledge_base @tool
│   └── hybrid_search.py       # HybridRetriever (BM25 + COSINE → RRF)
├── tools/
│   ├── datetime_tool.py       # 1 tool
│   ├── prometheus_tool.py     # 1 tool
│   ├── cls_logs_tool.py       # 2 tools
│   ├── k8s_tools.py           # 2 tools
│   ├── change_tools.py        # 1 tool
│   ├── slo_tools.py           # 1 tool
│   └── web_search_tool.py     # 1 tool (DuckDuckGo)
├── middleware/
│   ├── auth.py                # Pure ASGI API Key auth
│   ├── rate_limit.py          # Pure ASGI sliding window
│   ├── logging.py             # Pure ASGI structured logging
│   └── error_handler.py       # Global exception handler
├── notify/
│   └── dingtalk.py            # DingTalk markdown notification
├── session/manager.py         # MySQL/Redis/SQLite + compression + tool cache
├── ingestion/                 # chunker → embedder → indexer
├── skills/loader.py           # .claude/skills/*/SKILL.md loader
├── api/
│   ├── chat.py                # /chat + /chat_stream + /chat/clear + /chat/session/{id}
│   ├── aiops.py               # /ai_ops + /ai_ops/webhook + /ai_ops/templates
│   ├── admin.py               # /login + /admin/stats + /admin/tenants
│   ├── knowledge.py           # /knowledge/confirm (RBAC)
│   ├── metrics.py             # /metrics (Prometheus)
│   ├── upload.py              # /upload
│   ├── health.py              # /milvus/health
│   └── session.py             # Session routes
└── models/schemas.py          # Pydantic v2 models

tests/
├── conftest.py                # Shared fixtures
├── test_core.py               # Intent + session + health
├── test_intent.py             # Intent recognition
├── test_session.py            # Session lifecycle
├── test_imports.py            # Import verification
├── agent/test_aggregator.py   # Alert aggregator
├── api/test_endpoints.py      # HTTP endpoint tests
├── tools/test_tools.py        # Tool mock validation
└── eval/                      # RAG evaluation (10 queries)

.claude/
├── skills/                    # 7 progressive disclosure skills
├── tenants.json               # Multi-tenant key config
└── settings.json              # Plugin registry

Dockerfile                     # 2-stage (builder → runtime, non-root)
docker-compose.yml             # 9 containers
docker-compose.prod.yml        # Production overrides
Makefile                       # 12 targets
alembic/                       # DB migration framework
.github/workflows/ci.yml       # CI: syntax check + pytest
```

---

## 路线图

| 阶段 | 状态 | 交付 |
|---|---|---|
| P0 | done | API auth, rate limit, error handling, logging, CI/CD, Docker hardening |
| P1 | done | IM notify, alert aggregation, K8s Events, patrol, graded runbooks, knowledge deposition |
| P2 | done | Integration tests, Alembic, multi-env, change correlation, connection pool fix |
| P3 | done | Multi-tenant + RBAC, SLO, self-monitor, web search, 2-layer intent routing |

---

## 关键配置

```ini
# LLM
DEEPSEEK_API_KEY=sk-xxx

# Embedding
DASHSCOPE_API_KEY=sk-xxx

# Milvus
MILVUS_HOST=standalone
MILVUS_PORT=19530

# Storage
SESSION_BACKEND=mysql
MYSQL_HOST=mysql
REDIS_URL=redis://redis:6379/0

# Modes
PROMETHEUS_MOCK_ENABLED=true
CLS_MOCK_ENABLED=true
K8S_MOCK_ENABLED=true

# Intent
INTENT_CONFIDENCE_THRESHOLD=0.05

# Multi-tenant
API_KEYS=                    # comma-separated (fallback)
WEBHOOK_SECRET=
DINGTALK_WEBHOOK_URL=
```
