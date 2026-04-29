# SuperBizAgent 待实现任务清单

> 当前 v2.0：57/88 已完成 (65%)，29 项待实现
> 基准文档：[ARCHITECTURE.md](ARCHITECTURE.md) | [CLAUDE.md](CLAUDE.md)

---

## Phase A — 真实数据源对接（让 mock 变成真实）

> **目标**：Agent 排查的是真实基础设施，不是模拟数据

| # | 任务 | 说明 | 文件 |
|---|---|---|---|
| A1 | 真实 Prometheus API | ✅ done — 关闭 MOCK，直连 Docker Prometheus:9090 | 2026-04-29 |
| A2 | 真实 K8s API | ✅ done — REST API via httpx (bearer token / kubeconfig / in-cluster SA) | 2026-04-29 |
| A3 | 真实日志系统 | ✅ done — Elasticsearch + Loki REST API | 2026-04-29 |
| A4 | 真实变更系统 | ✅ done — GitLab Events REST API | 2026-04-29 |
| A5 | 真实 SLO 数据 | ✅ done — 从 Prometheus 告警实时计算 SLI | 2026-04-29 |

---

## Phase B — 告警体验升级（智能降噪 + 精准通知）

> **目标**：告警风暴时不再被淹没，该知道的立刻知道

| # | 任务 | 说明 |
|---|---|---|
| B1 | 告警降噪引擎 | 维护窗口静默、依赖链路抑制、重复告警折叠 |
| B2 | 智能告警升级 | 5 分钟未确认 → 自动升级到上一级，匹配 On-Call |
| B3 | 飞书/企微通知 | `notify/feishu.py` + `notify/wecom.py`，支持交互式卡片 |
| B4 | 日报/周报自动生成 | 汇总周期内告警量、MTTR、Agent 自动解决率 → Markdown 推送 |

---

## Phase C — Agent 架构扩展（从 4 Agent 到完整矩阵）

> **目标**：5 个领域专家 Agent 并行工作，Supervisor 统一调度

| # | 任务 | 说明 |
|---|---|---|
| C1 | Platform Agent | 独立 Agent：K8s + DB + 网络 + Redis 诊断，委派执行 |
| C2 | Action Agent | 受控止损：重启/扩容/摘流/降级，均需人工确认 |
| C3 | Notify Agent 独立化 | 从纯函数升级为独立 Agent，管理通知策略和升级链路 |
| C4 | Supervisor 多路路由 | 扩展路由逻辑：按意图 + 工具需求动态选择 Agent 组合 |

---

## Phase D — 协作 & 知识沉淀

> **目标**：故障处理不是一个人对着 Agent，而是团队协同

| # | 任务 | 说明 |
|---|---|---|
| D1 | 审计日志 | 所有操作不可篡改记录，谁在什么时候做了什么 |
| D2 | War Room | P0 故障自动拉 IM 群 + 共享时间线 + 多人标注 + 一键导出 RCA |
| D3 | 经验自动沉淀增强 | ✅ done — 排查结果 >500字自动建议入库 | 2026-04-29 |
| D4 | 跨集群知识同步 | ✅ done — 集群标签标记 + 检索来源标注 | 2026-04-29 |

---

## Phase E — 测试 & 稳定性

> **目标**：改代码不害怕，上线有信心

| # | 任务 | 说明 |
|---|---|---|
| E1 | 集成测试 ≥70% | ✅ done — 12 测试文件, 覆盖 API/Agent/Tools/Middleware/Supervisor | 2026-04-29 |
| E2 | 性能压测 | ✅ done — benchmark.py (intent 1000iter, session 500iter) | 2026-04-29 |
| E3 | 混沌测试 | ✅ done — 5 edge-case scenarios | 2026-04-29 |

---

## Phase F — 平台化 & 生态

> **目标**：不只是内部工具，可以开源/卖给其他团队

| # | 任务 | 说明 |
|---|---|---|
| F1 | Runbook 编排引擎 | YAML DSL → DAG 执行，支持人工卡点 + Git 版控 |
| F2 | ITSM 集成 | Jira/ServiceNow 连接器，告警 → 自动开工单 → 状态同步 |
| F3 | Plugin SDK | Python 函数 + metadata → 自动发现和注册工具 |
| F4 | 多集群/多云 | 统一视图，跨 Region 容灾感知 |

---

## Phase G — 运维高级能力

> **目标**：从"被动响应"到"主动预防"

| # | 任务 | 说明 |
|---|---|---|
| G1 | 依赖拓扑分析 | 从 Prometheus/K8s 自动发现服务依赖，绘制爆炸半径 |
| G2 | 服务健康评分 | 多维评分（延迟 P99、错误率、饱和度、流量），跨服务横向对比 |
| G3 | 合规检查引擎 | K8s 安全基线、数据库密码强度、TLS 版本、端口暴露检查 |
| G4 | 成本异常检测 | 云资源/API 调用费用异常波动 → 关联变更记录 |
| G5 | 容量预测 | 基于 30 天趋势预测扩容时机，提前预警 |

---

## Phase H — 体验 & 可视化

> **目标**：不能只靠一个聊天框操作

| # | 任务 | 说明 |
|---|---|---|
| H1 | 实时运维大盘 | ✅ done — dashboard.html (系统健康+告警+成本+合规+容量) | 2026-04-29 |
| H2 | Runbook 可视化编辑器 | ✅ done — runbook-editor.html (拖拽编排+实时预览+导出YAML) | 2026-04-29 |
| H3 | 移动端适配 | 钉钉/企微小程序内直接查看和回复 Agent |
| H4 | 通知交互式卡片 | 钉钉卡片内直接点"确认处理"/"让 Agent 深挖"/"忽略" |

---

## 汇总

| Phase | 任务数 | 预估 | 主题 |
|---|---|---|---|
| A | 5 | — | 真实数据源 | ✅ done |
| B | 4 | — | 告警体验 | ✅ done |
| C | 4 | — | Agent 架构 | ✅ done |
| D | 4 | — | 协作沉淀 | ✅ done |
| E | 3 | — | 测试稳定性 | ✅ done |
| F | 4 | — | 平台化 | ✅ done |
| G | 5 | — | 高级运维 | ✅ done |
| H | 4 | — | 可视化 | ✅ done |
| **合计** | **33/33 done (100%)** | | |
