# SuperBizAgent 架构

> 最后更新: 2026-04-26 | 状态: 完整交付

---

## 全景

```
                        POST /api/chat {Id, Question}
                                   │
                                   ▼
                        ┌──────────────────┐
                        │   IntentGateway   │  app/rag/intent.py
                        │   规则引擎预分类    │  keyword(0.6)+pattern(0.4)
                        │                  │
                        │  score ≤ 0       │→ block (0 LLM cost)
                        │  score > 0       │→ pass
                        └────────┬─────────┘
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
                  │  Mixed           → rag→sre│
                  │                          │
                  │  + Skills injection       │
                  │  + Intent context hints    │
                  └──────┬──────────┬────────┘
                         │          │
             ┌───────────┘          └───────────┐
             ▼                                   ▼
  ┌──────────────────────┐          ┌──────────────────────┐
  │   RAG Agent           │          │   SRE Agent           │
  │   react_agent.py      │          │   react_agent.py      │
  │                      │          │                      │
  │ LLM: DeepSeek        │          │ LLM: DeepSeek        │
  │      deepseek-chat   │          │      deepseek-chat   │
  │      T=0.7, 2000tk   │          │      T=0.3, 8000tk   │
  │                      │          │                      │
  │ Tools (2):           │          │ Tools (5):           │
  │  search_knowledge    │          │  search_knowledge    │
  │    _base (hybrid)    │          │    _base (hybrid)    │
  │  get_current         │          │  get_current         │
  │    _datetime         │          │    _datetime         │
  │                      │          │  query_prometheus    │
  │                      │          │  query_logs          │
  │                      │          │  get_available       │
  │                      │          │    _log_topics       │
  │                      │          │                      │
  │                      │          │ Skills injected:     │
  │                      │          │  log-analyzer        │
  │                      │          │  alert-triage        │
  └──────────┬───────────┘          └──────────┬───────────┘
             │                                  │
             └────────────┬─────────────────────┘
                          │
             ┌────────────┴────────────┐
             │      共享基础设施         │
             │                         │
             │ ┌─────────────────────┐ │
             │ │ HybridRetriever     │ │  app/rag/hybrid_search.py
             │ │ BM25 + Milvus COSINE│ │
             │ │ → RRF fusion        │ │
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ SessionStore        │ │  app/session/manager.py
             │ │ MySQL + Redis       │ │  MySQL (持久化会话/消息)
             │ │ + asyncio           │ │  Redis (工具缓存 5min TTL)
             │ │ Context compression  │ │  Session (内存, fast)
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ SkillLoader         │ │  app/skills/loader.py
             │ │ .claude/skills/     │ │
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ Task Templates (4)  │ │  app/agent/task_templates.py
             │ │ CPU/内存/慢响应/宕机 │ │
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ Logging             │ │  Python logging module
             │ │ Structured format   │ │
             │ └─────────────────────┘ │
             └─────────────────────────┘
```

---

## 三个 Agent 职责矩阵

```
┌──────────────────┬──────────────┬──────────────┬──────────────┐
│                  │  Supervisor  │  RAG Agent   │  SRE Agent   │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 文件              │ supervisor.py│ react_agent  │ react_agent  │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ LLM              │ DeepSeek     │ DeepSeek     │ DeepSeek     │
│ temperature      │ 0.01         │ 0.7          │ 0.3          │
│ max_tokens       │ 200          │ 2000         │ 8000         │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 工具数            │ 0            │ 2            │ 5            │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 决策空间          │ 路由 + 串行   │ 是否检索      │ 多工具排查    │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 输出             │ 路由决策      │ 技术回答     │ Markdown 报告 │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ Skills 注入      │ 无           │ 通常无       │ log-analyzer  │
│                  │              │              │ alert-triage  │
├──────────────────┼──────────────┼──────────────┼──────────────┤
│ 调用次数/请求     │ 0-1          │ 1-3          │ 2-6          │
└──────────────────┴──────────────┴──────────────┴──────────────┘
```

## LLM & Embedding

```
Chat LLM:    DeepSeek deepseek-chat (via langchain-openai.ChatOpenAI)
              base_url: https://api.deepseek.com

Embedding:   DashScope text-embedding-v4 (1024-dim)
              app/ingestion/embedder.py → DashScopeEmbeddings

Vector DB:   Milvus 2.5.10 standalone (Docker)
              custom MilvusStore wrapper (not langchain-milvus)
              COSINE, enable_dynamic_field=True
```

## 数据流

### /api/chat (问答)

```
ChatRequest → IntentGateway.route()
  ├─ score ≤ 0  → block, return "我是运维助手..."
  └─ score > 0  → Supervisor.route()
                    ├─ Fast: IntentGateway confidence > 0.15 → rag/sre
                    └─ Slow: Supervisor LLM routing
                      → RAG Agent / SRE Agent invoke
                      → return answer
                      → session.compress_history() if > 6 pairs
```

### /api/ai_ops (告警排查 + SSE)

```
POST /api/ai_ops → Supervisor.astream(SRE_TASK)
  ├─ route → sre_agent (fixed)
  ├─ inject_context: IntentGateway prompt + matched Skills
  ├─ astream loop over ReAct events
  │   ├─ tool_calls → yield "🔧 调用工具: {name}"
  │   └─ ai.content (no tool_calls) → final_content
  ├─ yield final_content as 80-char SSE chunks
  ├─ save to long_term_memory
  └─ yield done
```

## 路由决策示例

```
"CPU 使用率过高怎么排查"
  → processed: "cpu使用率过高怎么排查"
  → troubleshooting: 关键词 "cpu"+"排查"+"过高" = 3/18 * 0.6 = 0.1
  → confidence 0.1 > 0.05 → pass
  → Supervisor: confidence 0.1 > 0.15? No → LLM route → "sre"
  → SRE Agent: query_prometheus → query_logs → search_knowledge_base → 报告

"Redis 怎么配置持久化"
  → configuration: "配置"+"部署" = 2/9 * 0.6 = 0.133 + pattern 0.4 = 0.533
  → Supervisor: confidence 0.533 > 0.15 → "rag"
  → RAG Agent: search_knowledge_base → 回答

"今天天气怎么样"
  → all scores = 0.0
  → IntentGateway: score ≤ 0 → block
  → "我是运维助手，只能回答运维和技术相关的问题。" (0 LLM calls)
```

## 端点

```
POST /api/chat                      Supervisor → Agent → answer
POST /api/chat_stream               SSE streaming variant
POST /api/ai_ops                    Supervisor → SRE Agent → SSE(工具+报告)
GET  /api/ai_ops/templates          任务模板列表
POST /api/ai_ops/template/{key}    按模板运行 AIOps
POST /api/upload                    上传文件 → IndexingService → Milvus
POST /api/ai_ops/webhook            Alertmanager webhook → auto SRE Agent
GET  /milvus/health                 {milvus, deepseek, vector_count}
POST /api/chat/clear                清空会话
GET  /api/chat/session/{id}         会话信息
GET  /                              前端界面
```

## 文件结构

```
app/
├── main.py                    # FastAPI lifespan + logging + auto-ingestion
├── config.py                  # pydantic-settings: DeepSeek + DashScope + Milvus
├── agent/
│   ├── supervisor.py          # Supervisor: 2-tier routing + skill injection
│   ├── react_agent.py         # build_rag_agent() + build_sre_agent()
│   ├── tools.py               # gather_rag_tools() + gather_sre_tools()
│   └── task_templates.py      # 4 preset AIOps prompts
├── rag/
│   ├── intent.py              # IntentRecognizer + IntentGateway + AgentConfig
│   ├── retrieval.py           # MilvusStore (pymilvus direct, no langchain-milvus)
│   ├── rag_tool.py            # search_knowledge_base @tool (hybrid search)
│   └── hybrid_search.py       # HybridRetriever (BM25 + Milvus COSINE → RRF)
├── tools/
│   ├── datetime_tool.py       # get_current_datetime (Asia/Shanghai)
│   ├── prometheus_tool.py     # query_prometheus_alerts (mock/real)
│   └── cls_logs_tool.py       # query_logs + get_available_log_topics (mock)
├── skills/loader.py           # .claude/skills/*/SKILL.md → match + inject
├── session/manager.py         # SQLite + asyncio.Lock + 上下文压缩 + tool_cache
├── ingestion/                 # chunker → embedder(DashScope) → indexer
├── api/                       # chat, aiops, upload, health, session
└── models/schemas.py          # Pydantic v2 request/response

tests/
├── test_core.py               # 10 条核心测试
└── eval/                      # 10 条标注查询 + evaluator.py
.claude/skills/                # log-analyzer, alert-triage
docker-compose.yml             # Milvus + etcd + minio + attu + app + prometheus
Dockerfile                     # Single-stage Python 3.12
Makefile                       # make init / up / down / logs / status / reindex
```

## 关键配置 (.env / config.py)

```ini
# LLM
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat

# Embedding
DASHSCOPE_API_KEY=sk-xxx
DASHSCOPE_EMBEDDING_MODEL=text-embedding-v4

# Milvus
MILVUS_HOST=standalone (Docker) / localhost (dev)
MILVUS_PORT=19530

# Modes
PROMETHEUS_MOCK_ENABLED=true
CLS_MOCK_ENABLED=true

# Storage
SESSION_BACKEND=mysql            # Docker: mysql, Dev: sqlite
MYSQL_HOST=mysql                 # Docker service name
MYSQL_USER=superbiz
MYSQL_DATABASE=superbiz
REDIS_URL=redis://redis:6379/0   # Tool cache (5min TTL)

# Intent
INTENT_CONFIDENCE_THRESHOLD=0.05
```
