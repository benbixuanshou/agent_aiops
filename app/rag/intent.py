from dataclasses import dataclass, field
from enum import Enum
import re
from pydantic import BaseModel
from typing import Optional

from app.config import settings


class IntentType(str, Enum):
    TECHNICAL_QUESTION = "technical_question"
    CONFIGURATION = "configuration"
    PRODUCT_INQUIRY = "product_inquiry"
    TROUBLESHOOTING = "troubleshooting"
    GENERAL_QUESTION = "general_question"


class IntentResult(BaseModel):
    intent: IntentType
    confidence: float


class IntentRecognizer:
    """
    Rule-based intent recognizer.
    Ported from Java IntentRecognitionService:
    - Keyword matching (60% weight)
    - Regex pattern matching (40% weight)
    """

    def __init__(self):
        # ── 第一层：通用相关性词库（全类别共享） ──
        # 命中 ≥1 个词 = 放行；全部 0 命中 = 拦截
        self.relevance_keywords: set[str] = {
            # 基础设施
            "服务", "接口", "api", "请求", "调用", "响应", "返回", "http",
            "服务器", "主机", "节点", "集群", "负载", "代理", "网关",
            "域名", "dns", "ip", "端口", "防火墙", "路由",
            # 数据库 & 缓存
            "数据库", "mysql", "redis", "mongodb", "postgresql", "sql",
            "索引", "查询", "写入", "事务", "锁", "表", "连接池", "慢查询",
            "缓存", "消息队列", "kafka", "mq", "rabbitmq",
            # 容器 & 编排
            "docker", "k8s", "kubernetes", "pod", "容器", "镜像", "deployment",
            "namespace", "ingress", "service", "编排",
            # 监控 & 日志
            "日志", "监控", "告警", "报警", "指标", "metric", "dashboard",
            "prometheus", "grafana", "trace", "链路", "采样",
            # 故障 & 排查
            "错误", "异常", "故障", "报错", "崩溃", "超时", "失败",
            "泄漏", "溢出", "oom", "死锁", "重启", "挂掉", "不可用",
            "恢复", "排查", "修复", "处理", "解决", "怎么办",
            "cpu", "内存", "磁盘", "网络", "io", "吞吐", "延迟",
            "5xx", "500", "502", "503", "504", "4xx",
            # 部署 & 变更
            "部署", "发布", "上线", "回滚", "配置", "升级", "扩容", "缩容",
            "变更", "灰度", "版本", "环境",
            # 开发 & 技术
            "代码", "编程", "实现", "开发", "架构", "设计", "优化",
            "线程", "进程", "并发", "异步", "框架", "依赖",
        }

        self.keywords = {
            IntentType.TECHNICAL_QUESTION: [
                "如何实现", "怎么实现", "技术原理", "原理", "算法",
                "实现", "代码", "编程", "开发", "技术",
                "架构", "设计", "方案", "最佳实践", "优化", "区别",
                "是什么", "怎么用", "作用", "用法", "概念",
            ],
            IntentType.CONFIGURATION: [
                "配置", "设置", "部署", "安装", "配置文件",
                "环境变量", "参数", "选项", "配置步骤", "调参",
                "版本", "升级", "更新", "依赖",
            ],
            IntentType.PRODUCT_INQUIRY: [
                "功能", "特性", "优势", "价格", "使用方法", "产品介绍", "产品",
            ],
            IntentType.TROUBLESHOOTING: [
                "错误", "异常", "问题", "故障", "报错", "崩溃",
                "性能", "慢", "超时", "无法", "失败", "怎么办",
                "排查", "过高", "占用", "cpu", "内存", "磁盘",
                "oom", "泄漏", "挂掉", "不可用", "down", "死机",
                "重启", "卡住", "502", "503", "500", "救急",
                "怎么解决", "处理", "修复", "恢复", "原因",
                "数据库", "连接池", "死锁", "慢查询", "高并发",
                "网络", "延迟", "超时", "丢包", "拒绝连接",
                "docker", "k8s", "kubernetes", "pod", "容器",
                "redis", "mysql", "nginx", "kafka", "mq",
                "接口", "api", "请求", "调用", "返回",
                "日志", "监控", "报警", "告警", "指标",
                "堆", "栈", "dump", "gc", "线程池",
            ],
        }

        self.patterns = {
            IntentType.TECHNICAL_QUESTION: [
                re.compile(r".*如何.*实现.*"),
                re.compile(r".*怎么.*实现.*"),
                re.compile(r".*技术.*原理.*"),
                re.compile(r".*什么.*是.*"),
                re.compile(r".*区别.*"),
            ],
            IntentType.CONFIGURATION: [
                re.compile(r".*如何.*配置.*"),
                re.compile(r".*怎么.*设置.*"),
                re.compile(r".*部署.*步骤.*"),
            ],
            IntentType.PRODUCT_INQUIRY: [
                re.compile(r".*有哪些.*功能.*"),
                re.compile(r".*有哪些.*特性.*"),
                re.compile(r".*产品.*功能.*"),
            ],
            IntentType.TROUBLESHOOTING: [
                re.compile(r".*出现.*错误.*"),
                re.compile(r".*发生.*异常.*"),
                re.compile(r".*性能.*问题.*"),
                re.compile(r".*为什么.*(慢|失败|报错|超时).*"),
                re.compile(r".*如何.*排查.*"),
                re.compile(r".*怎么.*(排查|解决|处理|修复).*"),
                re.compile(r".*cpu.*高.*"),
                re.compile(r".*内存.*(高|满|泄漏|不足|溢出).*"),
                re.compile(r".*连接.*(池|超时|失败|耗尽).*"),
                re.compile(r".*数据.*(库|库连接|查询).*(慢|超时|失败|多).*"),
                re.compile(r".*pod.*(重启|crash|pending|异常).*"),
                re.compile(r".*服务.*(挂|不可用|异常|报错|500|503).*"),
                re.compile(r".*磁盘.*(满|不足|高|90).*"),
            ],
        }

    def recognize(self, query: str) -> IntentResult:
        if not query or not query.strip():
            return IntentResult(intent=IntentType.GENERAL_QUESTION, confidence=0.0)

        if not settings.intent_enabled:
            return IntentResult(intent=IntentType.GENERAL_QUESTION, confidence=0.0)

        processed = self._preprocess(query)
        scores: dict[IntentType, float] = {}

        for intent in IntentType:
            if intent == IntentType.GENERAL_QUESTION:
                continue
            scores[intent] = self._calculate_score(processed, intent)

        best_intent = IntentType.GENERAL_QUESTION
        highest_score = 0.0

        for intent, score in scores.items():
            if score > highest_score:
                highest_score = score
                best_intent = intent

        if highest_score < settings.intent_confidence_threshold:
            return IntentResult(intent=IntentType.GENERAL_QUESTION, confidence=highest_score)

        return IntentResult(intent=best_intent, confidence=highest_score)

    def _preprocess(self, query: str) -> str:
        """Preprocess query: lowercase, strip punctuation, collapse whitespace"""
        query = query.lower()
        query = re.sub(r"[^\w\s]", " ", query)
        query = re.sub(r"\s+", " ", query).strip()
        return query

    def _calculate_score(self, query: str, intent: IntentType) -> float:
        """Calculate intent score: keywords 0.6 + patterns 0.4"""
        score = 0.0

        # Keyword matching (60%)
        keywords = self.keywords.get(intent, [])
        if keywords:
            match_count = sum(1 for kw in keywords if kw in query)
            score += (match_count / len(keywords)) * 0.6

        # Pattern matching (40%)
        patterns = self.patterns.get(intent, [])
        for pattern in patterns:
            if pattern.match(query):
                score += 0.4
                break

        return min(1.0, score)

    def check_relevance(self, query: str) -> int:
        """Check whether a query is potentially relevant.

        Returns 0 for truly irrelevant / gibberish, ≥1 for anything that may
        have a legitimate answer — either via internal KB or web search.

        Logic:
          1. Exact keyword hit → instant pass
          2. No keyword hit but ≥ 6 meaningful chars → weak pass (let web_search handle it)
          3. No keyword hit AND too short → block (gibberish like "asdf")
        """
        processed = self._preprocess(query)
        hits = sum(1 for kw in self.relevance_keywords if kw in processed)
        if hits > 0:
            return hits
        # Natural-language fallback: short random strings get blocked,
        # but sentences without technical terms still pass (→ web_search).
        meaningful = len(processed.replace(" ", ""))
        return 1 if meaningful >= 6 else 0


@dataclass
class AgentConfig:
    """Configuration for an Agent based on intent recognition result."""
    intent: IntentType
    tools: list = field(default_factory=list)
    prompt_extension: str = ""
    block: bool = False
    block_reply: Optional[str] = None
    weak_relevance: bool = False


class IntentGateway:
    """
    Intent recognition gateway — two-layer design.

    Layer 1 (relevance): generic tech keyword set (~100 terms).
      - 0 matches → truly irrelevant → block (save LLM cost).
      - ≥1 matches → pass through.

    Layer 2 (intent): per-category keywords + patterns → intent score.
      - score > 0.05 → strong relevance → internal KB first, then web.
      - score ≤ 0.05 → weak relevance → skip internal KB, web_search directly.
    """

    def __init__(self, intent_recognizer: "IntentRecognizer" = None):
        self.recognizer = intent_recognizer or IntentRecognizer()

    def route(self, query: str) -> AgentConfig:
        relevance = self.recognizer.check_relevance(query)

        # Layer 1: zero relevance → block
        if relevance == 0:
            return AgentConfig(
                intent=IntentType.GENERAL_QUESTION,
                block=True,
                block_reply=(
                    "我是运维助手，暂时无法回答这个问题。你可以尝试用运维相关的关键词描述问题，比如："
                    "CPU、内存、数据库、Docker、K8s、接口报错等服务相关的术语"
                ),
            )

        intent_result = self.recognizer.recognize(query)

        # Layer 2: intent score determines strategy
        weak = intent_result.confidence < settings.intent_confidence_threshold

        if weak:
            return AgentConfig(
                intent=IntentType.GENERAL_QUESTION,
                weak_relevance=True,
                prompt_extension=(
                    "【注意】这个问题与运维的直接关联度较低，内部知识库大概率没有答案。"
                    "请跳过 search_knowledge_base，直接调用 web_search 进行联网搜索。"
                    "找到结果后，清晰标注：「此答案来自网络搜索，内部知识库未收录，仅供参考。」"
                ),
            )

        configs = {
            IntentType.TROUBLESHOOTING: AgentConfig(
                intent=intent_result.intent,
                prompt_extension="这是故障排查类问题，请优先查询告警和日志，然后查知识库找解决方案。",
            ),
            IntentType.TECHNICAL_QUESTION: AgentConfig(
                intent=intent_result.intent,
                prompt_extension="这是技术问题，请先查知识库获取技术细节。",
            ),
            IntentType.CONFIGURATION: AgentConfig(
                intent=intent_result.intent,
                prompt_extension="这是配置问题，请查知识库获取配置步骤和最佳实践。",
            ),
            IntentType.PRODUCT_INQUIRY: AgentConfig(
                intent=intent_result.intent,
                prompt_extension="这是产品咨询，请查知识库获取产品信息。",
            ),
            IntentType.GENERAL_QUESTION: AgentConfig(
                intent=intent_result.intent,
                prompt_extension="这是通用问题，可用知识库作为参考。",
            ),
        }

        return configs.get(intent_result.intent, configs[IntentType.GENERAL_QUESTION])
