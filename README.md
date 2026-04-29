# SuperBizAgent

> 基于 LangChain + LangGraph + FastAPI 的企业级多 Agent 智能运维平台

**当前版本: v0.1 | 目标版本: v2.0（企业交付）**

## 项目定位

面向团队内部的智能运维平台。核心场景：

- **告警来了** → Agent 自动排查 → 根因分析 → 处理建议 → 推送到 IM
- **遇到问题了** → 自然语言描述 → Agent 查知识库/查指标/查日志 → 给出答案
- **定时巡检** → 主动发现问题 → 不等告警才管
- **人走了经验还在** → 排查过的方案自动沉淀到知识库

## 架构亮点

```
IntentGateway ──→ Supervisor ──→ RAG Agent     (技术问答)
                      │           SRE Agent     (告警排查)
                      │
              零分查询直接拦截 (0 LLM 调用)
              RAG 检索: BM25 + Milvus COSINE → RRF 融合
              上下文自动压缩: 6 对 → LLM 摘要
              8 个渐进式 Skills (含 garden-skills)
```

- **Supervisor + 2 Workers** 多 Agent 架构，LangGraph `create_react_agent` 驱动
- **Agentic RAG**: LLM 自主决定何时检索知识库，非固定管线
- **混合检索**: BM25 关键词 + 向量相似度 → RRF 融合，Recall@5 = 1.0, MRR = 0.933
- **DeepSeek** 作为 LLM，DashScope 作为嵌入模型，Milvus 作为向量库
- **8 个 Skills** (`.claude/skills/`): 5 个运维专属 + 3 个通用（garden-skills）
- **MySQL + Redis** 双存储: Session 持久化 + 工具缓存
- **Alertmanager Webhook** 自动触发 Agent 排查
- **Docker Compose** 一键部署全栈（7 个容器）

## 快速开始

```bash
make init     # 一键启动全部服务
# 浏览器打开 http://localhost:9900
```

```bash
make down     # 停止
make logs     # 日志
make check    # 健康检查
```

## 技术栈

| 层 | 技术 |
|---|------|
| LLM | DeepSeek (deepseek-chat) |
| 嵌入 | DashScope text-embedding-v4 (1024-dim) |
| Agent 框架 | LangGraph 0.2+ (`create_react_agent`) |
| 向量库 | Milvus 2.5, COSINE, IVF_FLAT |
| 混合检索 | rank-bm25 + Milvus → RRF |
| Web | FastAPI + SSE 流式 + Static |
| 存储 | MySQL 8.0 + Redis 7 (Docker) / SQLite (dev) |
| 监控 | Prometheus + Alertmanager (mock/real 可切换) |
| 部署 | Docker Compose 全容器化 |

## 项目结构

```
app/
├── agent/            # Supervisor + RAG Agent + SRE Agent
├── rag/              # IntentGateway, HybridSearch, MilvusStore
├── tools/            # Prometheus(mock/real), CLS logs(mock), Datetime
├── session/          # MySQL/Redis/SQLite + 上下文压缩
├── skills/           # .claude/skills/ loader
├── api/              # chat, aiops, upload, health, session
├── ingestion/        # chunker → embedder → indexer
└── models/schemas.py # Pydantic v2

.claude/skills/       # 8 个渐进式 Skills
tests/                # 核心测试 + RAG 评测
```

## 端点

| 端点 | 功能 |
|---|---|
| `POST /api/chat` | 问答 (Supervisor → RAG/SRE Agent) |
| `POST /api/chat_stream` | 流式问答 (SSE) |
| `POST /api/ai_ops` | AIOps 告警排查 (SSE + 工具调用进度) |
| `POST /api/ai_ops/webhook` | Alertmanager Webhook 自动触发 Agent |
| `GET /api/ai_ops/templates` | 任务模板列表 (8模板, P0/P1/P2) |
| `POST /api/knowledge/confirm` | 确认排查结果入库 |
| `POST /api/upload` | 上传文档自动向量化 |
| `GET /milvus/health` | 健康检查 (+ Agent 自监控指标) |
| `GET /metrics` | Prometheus 指标导出 |
| `GET /docs` | OpenAPI Swagger 文档 |
| `GET /` | Web 前端 |

## 生产部署

```bash
# 开发环境
make init                 # 一键启动 (mock 模式)
docker compose up -d       # 手动启动

# 生产环境
cp .env .env.prod  # 编辑生产配置 (APP_ENV=prod, API keys, mock=false)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

**环境变量说明：**

| 变量 | 说明 | 默认值 |
|---|---|---|
| `APP_ENV` | 运行环境 dev/staging/prod | dev |
| `API_KEYS` | 逗号分隔的 API Key (prod 必填) | 空 (dev 免认证) |
| `WEBHOOK_SECRET` | Alertmanager HMAC 密钥 | 空 |
| `DINGTALK_WEBHOOK_URL` | 钉钉群机器人地址 | 空 |
| `PATROL_INTERVAL_MINUTES` | 巡检间隔分钟数 (0=关闭) | 15 |

详见 [ARCHITECTURE.md](ARCHITECTURE.md) — 完整架构、功能地图、环境变量表

## 路线图

| 阶段 | 状态 |
|---|---|
| **P0** — API 认证、限流、异常处理、日志、CI/CD、Docker 加固 | done |
| **P1** — IM 通知、告警聚合、K8s Events、巡检、分级 Runbook、知识沉淀 | done |
| **P2** — 测试、Alembic 迁移、多环境、变更关联、连接池修复 | done |
| **P3** — 多租户、审计、SLO、自监控、War Room、Runbook、ITSM、Plugin SDK | done |
