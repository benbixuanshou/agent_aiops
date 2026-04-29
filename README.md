# SuperBizAgent

> 基于 LangChain + LangGraph + FastAPI 的企业级多 Agent 智能运维平台

**版本: v2.0 | 状态: 内部可用**

## 项目定位

面向团队内部的智能运维平台：

- **告警来了** → Agent 自动排查 → 根因分析 → 处理建议 → 推送到 IM
- **遇到问题了** → 自然语言描述 → Agent 查知识库 → 无则联网搜索 → 标注来源
- **定时巡检** → 主动发现问题 → 不等告警才管
- **人走了经验还在** → 排查过的方案确认后自动沉淀到知识库

## 架构亮点

```
IntentGateway(两层) ──→ Supervisor ──→ RAG Agent(3 tools) — 技术问答 + 联网搜索
                              │           SRE Agent(9 tools) — 告警排查全链路
                              │
              相关性词库(~100词) + 意图分类 → 三档路由
              强相关(内部KB优先) / 弱相关(直接联网) / 拦截
              BM25 + Milvus COSINE → RRF 融合
              多租户(RBAC) + Session 隔离 + 审计
```

- **Supervisor + 2 Workers**，LangGraph `create_react_agent`，全 ReAct 闭环
- **两层意图识别**：相关性词库(~100 词) + 意图分类 → 强/弱/拦截三档
- **联网搜索**：内部 KB 优先 → 无则 DuckDuckGo 联网 → 标注来源
- **9 容器 Docker Compose**：Milvus + MySQL + Redis + Prometheus + Alertmanager + App
- **多租户 + RBAC**：API Key → 租户绑定，admin/operator/viewer 三级
- **8 个渐进式 Skills**：`.claude/skills/*/SKILL.md`
- **混合检索**：BM25 + Milvus COSINE → RRF 融合，Recall@5 = 1.0

## 快速开始

```bash
make init     # 一键启动
# 浏览器打开 http://localhost:9900
# 登录: sk-team-a-admin / sk-team-a-operator / sk-team-b-admin
```

```bash
make down / restart / logs / check / clean / help
```

## 技术栈

| 层 | 技术 |
|---|---|
| LLM | DeepSeek (deepseek-v4-pro) |
| 嵌入 | DashScope text-embedding-v4 (1024-dim) |
| Agent | LangGraph 0.2+ (`create_react_agent`) |
| 向量库 | Milvus 2.5, COSINE, IVF_FLAT |
| 混合检索 | rank-bm25 + Milvus → RRF |
| Web | FastAPI + SSE + Static |
| 存储 | MySQL 8.0 + Redis 7 / SQLite (dev) |
| 监控 | Prometheus + Alertmanager |

## 端点

| 端点 | 功能 |
|---|---|
| `POST /api/chat` | 智能问答 |
| `POST /api/chat_stream` | SSE 流式问答 |
| `POST /api/ai_ops` | AIOps 排查 (SSE) |
| `POST /api/ai_ops/webhook` | Alertmanager 自动触发 |
| `GET /api/ai_ops/templates` | 任务模板 (8个, P0/P1/P2) |
| `POST /api/login` | 验证 API Key |
| `POST /api/knowledge/confirm` | 确认排查结果入库 |
| `POST /api/upload` | 上传文档向量化 |
| `GET /api/admin/stats` | 管理统计 (admin) |
| `GET /api/admin/tenants` | 租户信息 |
| `GET /milvus/health` | 健康检查 |
| `GET /metrics` | Prometheus 指标 |
| `GET /docs` | Swagger 文档 |
| `GET /` | Web 前端 |

## 路线图

| 阶段 | 状态 |
|---|---|
| **P0** — API 认证、限流、异常处理、日志、CI/CD、Docker 加固 | done |
| **P1** — IM 通知、告警聚合、K8s Events、巡检、分级 Runbook、知识沉淀 | done |
| **P2** — 测试、Alembic 迁移、多环境、变更关联、连接池修复 | done |
| **P3** — 多租户、SLO、自监控、War Room 骨架、Plugin SDK 骨架 | done |

详见 [ARCHITECTURE.md](ARCHITECTURE.md) — 完整架构、目标 Agent 体系、功能地图
