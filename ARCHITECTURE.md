# SuperBizAgent 架构

> 最后更新: 2026-04-28 | 状态: v0.1 (内部开发中)

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
             │ │ Context compression  │ │
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ SkillLoader         │ │  app/skills/loader.py
             │ │ .claude/skills/     │ │  8 个渐进式 Skills
             │ └─────────────────────┘ │
             │ ┌─────────────────────┐ │
             │ │ Task Templates (4)  │ │  app/agent/task_templates.py
             │ └─────────────────────┘ │
             └─────────────────────────┘
```

---

## Agent 职责矩阵（当前 v0.1）

| | Supervisor | RAG Agent | SRE Agent |
|---|---|---|---|
| 文件 | `supervisor.py` | `react_agent.py` | `react_agent.py` |
| LLM | DeepSeek T=0.01 | DeepSeek T=0.7 | DeepSeek T=0.3 |
| max_tokens | 200 | 2000 | 8000 |
| 工具数 | 0 | 3 | 9 |
| 决策空间 | 路由 + 串行 | 是否检索 | 多工具排查 |
| 输出 | 路由决策 | 技术回答 | Markdown 报告 |

---

## LLM & Embedding

```
Chat LLM:    DeepSeek deepseek-chat (via langchain-openai.ChatOpenAI)
              base_url: https://api.deepseek.com

Embedding:   DashScope text-embedding-v4 (1024-dim)

Vector DB:   Milvus 2.5.10 standalone (Docker)
              custom MilvusStore wrapper (not langchain-milvus)
              COSINE, IVF_FLAT, nprobe=10, enable_dynamic_field=True
```

---

## Skills 清单（8 个）

**运维专用（5 个）：**

| Skill | 触发场景 |
|---|---|
| `alert-triage` | 多条告警同时触发，需分级分类 |
| `log-analyzer` | 错误日志查询、异常堆栈分析、故障时间线 |
| `report-writer` | Agent 完成排查，准备输出最终报告 |
| `sql-tuning` | 慢查询、连接池耗尽、查询超时 |
| `capacity-planning` | CPU/内存持续高负载、需要扩容建议 |

**通用类（3 个，来自 garden-skills）：**

| Skill | 触发场景 |
|---|---|
| `rag-skill` | 本地 PDF/Excel 文档检索问答 |
| `gpt-image-2` | 图像生成/编辑，70+ 提示词模板 |
| `web-design-engineer` | Web 前端可视化（页面/仪表盘/原型） |

---

## 数据流

### /api/chat (问答)

```
ChatRequest → IntentGateway.route()
  ├─ score ≤ 0  → block, return "我是运维助手..."
  └─ score > 0  → Supervisor.route()
                    ├─ Fast: confidence > 0.15 → rag/sre
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
  ├─ save to tool cache (30-day TTL)
  └─ yield done
```

### /api/ai_ops/webhook (Alertmanager → 自动触发)

```
Alertmanager → POST /api/ai_ops/webhook
  ├─ extract firing alert names
  ├─ build SRE task: "收到 Prometheus 实时告警: {names}"
  ├─ Supervisor.invoke(task)
  └─ cache result → return {status, alerts}
```

---

## 目标架构 (v2.0 — 企业级)

> 当前 SRE Agent 5 个工具，扩展到 15-20 个工具时必须拆分

```
                         ┌─────────────────────┐
                         │     IntentGateway    │
                         │   (规则前置路由)      │
                         └────────┬────────────┘
                                  │
                         ┌────────▼────────────┐
                         │     Supervisor       │
                         │  (LLM 多路路由调度)   │
                         └──┬──┬──┬──┬──┬──┬──┘
                            │  │  │  │  │  │
              ┌─────────────┘  │  │  │  │  └─────────────┐
              ▼                ▼  ▼  ▼  ▼                ▼
     ┌────────────┐   ┌────────────┐   ┌──────────────────┐
     │ RAG Agent  │   │ SRE Agent  │   │ Platform Agent   │
     │ 知识检索    │   │ 告警排查    │   │ K8s/DB/基础设施   │
     │ 2 tools    │   │ 5 tools    │   │ 6-8 tools        │
     └────────────┘   └────────────┘   └──────────────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                      ┌────────▼────────┐    ┌─────────────────┐
                      │  Patrol Agent   │    │  Action Agent   │
                      │  定时巡检        │    │  受控自动止损    │
                      │  Cron 触发       │    │  需人工确认      │
                      └────────┬────────┘    └─────────────────┘
                               │
                      ┌────────▼────────┐
                      │  Notify Agent    │
                      │  通知/IM/推送    │
                      │  钉钉/企微/飞书   │
                      └─────────────────┘
```

### Agent 职责划分

| Agent | 职责 | 工具 | 触发方式 |
|---|---|---|---|
| **RAG Agent** | 知识库检索、技术问答 | search_kb, get_datetime | 用户提问、被其他 Agent 调用 |
| **SRE Agent** | 告警分类、关联聚合、根因分析、出报告 | Prometheus, logs, templates | Alertmanager、用户触发 |
| **Platform Agent** | K8s 诊断、DB 诊断、网络诊断、依赖拓扑 | kubectl events, mysql, redis, topology | SRE Agent 委派、定时巡检 |
| **Patrol Agent** | 定时巡检、趋势分析、证书过期检查 | Prometheus, K8s API, TLS check | Cron 定时触发 |
| **Action Agent** | 扩容、重启、摘流、降级开关 | scale, restart, drain, toggle | SRE/Patrol 建议 → 人工确认 |
| **Notify Agent** | 钉钉/企微推送、日报周报生成 | IM send, markdown render | 所有 Agent 的出口 |

### 设计原则
- Action Agent 永远需要人工确认（除非是明确的自动规则）
- Notify Agent 单向输出，只发消息不参与决策
- Platform Agent 并行查询多个数据源，汇总给 SRE Agent

---

## 完整功能地图

### 智能告警域
- 告警接入聚合 — 多条关联告警归并为 Incident
- 告警降噪抑制 — 维护窗口静默、依赖链路抑制、重复折叠
- 分级 Runbook — P0/P1/P2 不同处理策略
- SLO / 错误预算 — 预算消耗率监控，预算快烧完自动升级
- 预测性告警 — 趋势异常提前预警，不等阈值触发

### 智能排查域
- NL2Ops 自然语言运维 — "最近一周哪个服务最不稳定？"
- 多数据源诊断 — Prometheus + K8s + MySQL + Redis + Nginx
- 依赖拓扑分析 — 自动发现服务依赖 + 爆炸半径评估
- War Room 协同 — P0 故障自动拉群 + 共享时间线 + 多人标注
- 合规检查引擎 — 安全基线扫描 + 定期合规报告
- 变更关联分析 — 告警 + Git/发布记录关联

### 智能行动域
- 受控自动止损 — 重启/扩容/摘流/降级，需确认
- 灰度引流 — 异常 Pod 自动摘除
- Sandbox 预检 — 命令执行前检查是否为生产环境
- 自动 RCA 草稿 — 基于事件时间线生成根因分析初稿

### 主动巡检域
- 定时健康检查 — Cron 触发，主动发现问题
- 服务健康评分 — 多维评分（延迟/错误率/饱和度）
- 容量预测 — 基于 30 天趋势预测扩容时机
- 证书过期监控 — TLS/Secret/Token 到期预警
- 成本异常检测 — 云资源/API 费用异常波动

### 知识管理域
- RAG 混合检索 — BM25 + 向量 RRF 融合
- 经验自动沉淀 — 排查结果确认后写入知识库
- 跨集群知识同步 — 一个集群的经验全集群可用
- Runbook 版控 — Git 管理排查流程，灰度发布

### 协作 & 度量域
- IM 通知集成 — 钉钉/企微/飞书/Slack
- ITSM 工单集成 — Jira/ServiceNow 自动创建 + 状态同步
- On-Call 排班升级 — 值班 > 未确认 > 升级
- 移动端/语音接入 — TTS 朗读、截图分析
- 日报周报自动生成 — Markdown/PDF 推送
- 审计日志 — 不可篡改操作记录

### 平台 & 基础设施域
- 多租户隔离 — Team 级数据 + RBAC 权限
- 多集群/多云 — 统一视图 + 跨 Region 容灾
- API Key + 限流 + 认证
- 自监控自愈 — 平台自身健康 + LLM 调用成功率
- 高可用部署 — 无单点故障

---

## 路线图

| 阶段 | 目标 | 关键交付 |
|---|---|---|
| **P0 — 底线安全** | 可对外开放测试 | API 认证、限流、异常处理、日志系统、CI/CD |
| **P1 — 功能闭环** | 团队内部可用 | IM 通知、告警聚合、K8s Events、知识沉淀、定时巡检 |
| **P2 — 工程化** | 可对外交付 | 集成测试 70%+、Alembic 迁移、多环境、变更关联 |
| **P3 — 平台化** | 可商业交付 | 多租户、审计、ITSM、SLO、War Room、Runbook 编排、插件市场 |

---

## 端点

```
POST /api/chat                      Supervisor → Agent → answer
POST /api/chat_stream               SSE streaming variant
POST /api/ai_ops                    Supervisor → SRE Agent → SSE(工具+报告)
GET  /api/ai_ops/templates          任务模板列表 (8模板, P0/P1/P2)
POST /api/ai_ops/template/{key}    按模板运行 AIOps
POST /api/upload                    上传文件 → IndexingService → Milvus
POST /api/ai_ops/webhook            Alertmanager webhook → auto SRE Agent
POST /api/login                     验证 API Key → 返回租户信息
POST /api/knowledge/confirm         确认排查结果入库
GET  /api/admin/stats              全局统计 (admin only)
GET  /api/admin/tenants            当前租户信息
GET  /milvus/health                 {milvus, deepseek, vector_count, agent}
GET  /metrics                       Prometheus 指标
POST /api/chat/clear                清空会话
GET  /api/chat/session/{id}         会话信息
GET  /                              前端界面
```

---

## 文件结构

```
app/
├── main.py                    # FastAPI lifespan: embed → vector → hybrid → agents → supervisor
├── config.py                  # pydantic-settings: DeepSeek + Milvus + MySQL + Redis
├── tenant_store.py            # API Key → Tenant + Role 映射
├── self_monitor.py            # Agent 健康指标自监控
├── agent/
│   ├── supervisor.py          # 2-tier routing (rules + LLM), skill injection
│   ├── react_agent.py         # build_rag_agent() + build_sre_agent()
│   ├── tools.py               # gather_rag_tools() + gather_sre_tools()
│   ├── task_templates.py      # 8 preset AIOps prompts (P0/P1/P2)
│   ├── alert_aggregator.py    # 告警聚合引擎
│   └── agents/
│       └── patrol_agent.py    # 定时巡检 Agent
├── rag/
│   ├── intent.py              # IntentRecognizer(2层) + IntentGateway + AgentConfig
│   ├── retrieval.py           # MilvusStore (pymilvus direct)
│   ├── rag_tool.py            # search_knowledge_base @tool (hybrid search)
│   └── hybrid_search.py       # HybridRetriever (BM25 + Milvus COSINE → RRF)
├── tools/
│   ├── datetime_tool.py       # get_current_datetime
│   ├── prometheus_tool.py     # query_prometheus_alerts (mock/real)
│   ├── cls_logs_tool.py       # query_logs + get_available_log_topics (mock)
│   ├── k8s_tools.py           # query_k8s_events + get_k8s_namespaces (mock)
│   ├── change_tools.py        # query_recent_deployments (mock)
│   ├── slo_tools.py           # query_slo_status
│   └── web_search_tool.py     # DuckDuckGo 联网搜索
├── middleware/
│   ├── auth.py                # API Key 认证 (pure ASGI)
│   ├── rate_limit.py          # 滑动窗口限流 (Redis + memory fallback)
│   ├── logging.py             # 结构化日志 + Correlation ID
│   └── error_handler.py       # 全局异常处理
├── notify/
│   └── dingtalk.py            # 钉钉群机器人通知
├── session/manager.py         # MySQL/Redis/SQLite + context compression + tool cache
├── ingestion/                 # chunker → embedder(DashScope) → indexer
├── skills/loader.py           # .claude/skills/*/SKILL.md → match + inject
├── api/                       # chat, aiops, upload, health, session, metrics, admin, knowledge
└── models/schemas.py          # Pydantic v2 request/response

tests/
├── test_core.py               # 10 条核心测试
├── test_intent.py             # 意图识别测试
├── test_session.py            # Session 管理测试
├── test_imports.py            # 模块导入测试
├── conftest.py                # 共享 fixtures
├── agent/test_aggregator.py   # 告警聚合测试
├── api/test_endpoints.py      # HTTP 端点测试
├── tools/test_tools.py        # 工具 Mock 测试
└── eval/                      # RAG 评测 (Recall@5=1.0, MRR=0.933)

.claude/
├── skills/                    # 7 个渐进式 Skills
├── tenants.json               # 租户配置
└── settings.json              # Claude Code 插件配置

Dockerfile                     # 多阶段构建 (builder + runtime)
docker-compose.yml             # 9 services
docker-compose.prod.yml        # 生产环境覆盖
Makefile                       # 开发命令
alembic/                       # DB 迁移框架
```

## 关键配置

```ini
# LLM
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_MODEL=deepseek-chat

# Embedding
DASHSCOPE_API_KEY=sk-xxx

# Milvus
MILVUS_HOST=standalone
MILVUS_PORT=19530

# Storage
SESSION_BACKEND=mysql            # Docker: mysql, Dev: sqlite
MYSQL_HOST=mysql
REDIS_URL=redis://redis:6379/0

# Modes
PROMETHEUS_MOCK_ENABLED=true
CLS_MOCK_ENABLED=true

# Intent
INTENT_CONFIDENCE_THRESHOLD=0.05
```
