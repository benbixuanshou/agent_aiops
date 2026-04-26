# SuperBizAgent

> 基于 LangChain + LangGraph + FastAPI 的多 Agent 智能运维系统

## 架构亮点

```
IntentGateway ──→ Supervisor ──→ RAG Agent     (技术问答, 2 tools)
                      │           SRE Agent     (告警排查, 5 tools)
                      │
              零分查询直接拦截 (0 LLM 调用)
              RAG 检索: BM25 + Milvus COSINE → RRF 融合
              上下文自动压缩: 6 对 → LLM 摘要
```

- **Supervisor + 2 Workers** 多 Agent 架构，LangGraph `create_react_agent` 驱动
- **Agentic RAG**: LLM 自主决定何时检索知识库，非固定管线
- **混合检索**: BM25 关键词 + 向量相似度 → RRF 融合，**Recall@5 = 1.0, MRR = 0.933**
- **DeepSeek** 作为 LLM，DashScope 作为嵌入模型，Milvus 作为向量库
- **5 个 Skills** (`.claude/skills/`): 渐进式披露，按意图匹配注入 system prompt
- **上下文压缩**: 超过 6 轮对话自动 LLM 摘要，不丢历史
- **Docker 一键部署**: `make init` 启动全套（Milvus + App + Prometheus）

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
| 存储 | MySQL + Redis (会话 + 缓存) / SQLite (dev) |
| 部署 | Docker Compose 全容器化 |

## 项目结构

```
app/
├── agent/            # Supervisor + RAG Agent + SRE Agent
├── rag/              # IntentGateway, HybridSearch, MilvusStore
├── tools/            # Prometheus(mock/real), CLS(mock), Datetime
├── session/          # SQLite + 上下文压缩
├── skills/           # .claude/skills/ loader
├── api/              # chat, aiops, upload, health, session
└── ingestion/        # chunker → embedder → indexer
.claude/skills/       # log-analyzer, alert-triage, report-writer 等 5 个
tests/                # 核心测试 + RAG 评测 (Recall@5=1.0, MRR=0.933)
```

## 端点

| 端点 | 功能 |
|------|------|
| `POST /api/chat` | 问答 (Supervisor → RAG/SRE Agent) |
| `POST /api/chat_stream` | 流式问答 (SSE) |
| `POST /api/ai_ops` | AIOps 告警排查 (SSE, 工具调用+报告) |
| `POST /api/upload` | 上传文档自动向量化 |
| `GET /milvus/health` | 健康检查 (Milvus+DeepSeek+文档数) |
| `GET /` | Web 前端 (暗夜模式/拖拽上传/Ctrl+Enter) |

## 面试展示

```bash
make init                              # 启动
curl localhost:9900/milvus/health      # → {"milvus":"ok","deepseek":"ok","vector_count":268}
curl -X POST localhost:9900/api/chat   # → 完整告警分析报告
  -H "Content-Type: application/json"
  -d '{"Question":"CPU使用率过高怎么排查"}'
docker exec superbizagent poetry run python tests/eval/evaluator.py
# → Recall@5: 1.0, MRR: 0.933
```
