---
name: log-analyzer
description: >
  当用户需要分析应用日志、排查错误根因、聚类异常模式或重建故障时间线时使用。
  触发场景：错误日志查询、异常堆栈分析、故障时间线梳理、ConnectionPoolExhausted、OOM、慢查询等。
allowed-tools:
  - query_logs
  - get_available_log_topics
  - get_current_datetime
---

# 日志分析技能

## When to Use

- 用户报出具体错误信息（如 ConnectionPoolExhaustedException、OOM、NullPointerException）
- 需要排查某个服务在特定时间段内的异常行为
- 需要从多个日志来源对比找出故障的变化趋势
- 告警面板显示 CPU/内存/响应时间异常，需要日志佐证

## When NOT to Use

- 如果用户只是问概念性问题（"什么是 Full GC"），直接回答，不需要调工具
- 如果已经调过同一工具 3 次以上且都返回空结果，停止查询

## 调用流程

### Step 1: 获取可用的日志主题
调用 `get_available_log_topics`，了解当前有哪些日志主题可查。

### Step 2: 按优先级分级查询

1. **应用日志**（最高优先级）
   `query_logs(log_topic="application-logs", query="level:ERROR OR level:FATAL", limit=50)`
   如果有具体错误关键词，替换 query 中的泛用过滤条件。

2. **系统指标日志**（跟应用异常时间窗口对齐）
   `query_logs(log_topic="system-metrics", query="cpu_usage OR memory_usage", limit=30)`
   关注 CPU/内存指标在应用报错前后的变化趋势。

3. **数据库慢查询日志**（如果涉及 DB 超时）
   `query_logs(log_topic="database-slow-query", query="query_time:>1", limit=20)`

4. **系统事件日志**（如果怀疑 Pod 重启/OOM Kill）
   `query_logs(log_topic="system-events", query="restart OR oom_kill", limit=20)`

### Step 3: 错误聚类
将收集到的日志按 message 相似度分组：
- 合并含义相同的错误信息
- 统计每类错误的出现频次
- 提取 Top-3 高频错误模式

### Step 4: 时间线重建
- 将所有错误事件按时间排序
- 标注每个事件的首发时间
- 推断事件间的因果关系（A 导致 B？A 和 B 都源于 C？）

## 输出格式

```
## 日志分析结果

### 错误分布
| 错误类型 | 出现次数 | 首次时间 | 最近时间 |
|---------|---------|---------|---------|
| xxx     | N       | HH:MM   | HH:MM   |

### 故障时间线
1. [HH:MM] 第一个异常事件
2. [HH:MM] 第二个异常事件（由事件1导致/独立发生）
3. [HH:MM] 最终故障表现

### 根因线索
基于时间线相关性和错误模式分析，给出最可能的根因假设（2-3 句）。
```

## Advanced Usage

详细的错误模式库和解析脚本见 [references/error-patterns.md](references/error-patterns.md)。
