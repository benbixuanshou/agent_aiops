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
        self.keywords = {
            IntentType.TECHNICAL_QUESTION: [
                "如何实现", "怎么实现", "技术原理", "原理", "算法",
                "实现", "代码", "编程", "开发", "技术",
            ],
            IntentType.CONFIGURATION: [
                "配置", "设置", "部署", "安装", "配置文件",
                "环境变量", "参数", "选项", "配置步骤",
            ],
            IntentType.PRODUCT_INQUIRY: [
                "功能", "特性", "优势", "价格", "版本",
                "更新", "升级", "使用方法", "产品介绍", "产品", "功能特性",
            ],
            IntentType.TROUBLESHOOTING: [
                "错误", "异常", "问题", "故障", "报错",
                "崩溃", "性能", "慢", "超时", "无法", "失败",
                "排查", "过高", "占用", "cpu", "内存", "磁盘",
                "oom", "泄漏", "挂掉", "不可用", "down", "死机",
                "重启", "卡住", "502", "503", "500", "救急",
            ],
        }

        self.patterns = {
            IntentType.TECHNICAL_QUESTION: [
                re.compile(r".*如何.*实现.*"),
                re.compile(r".*怎么.*实现.*"),
                re.compile(r".*技术.*原理.*"),
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
                re.compile(r".*产品.*特性.*"),
            ],
            IntentType.TROUBLESHOOTING: [
                re.compile(r".*出现.*错误.*"),
                re.compile(r".*发生.*异常.*"),
                re.compile(r".*性能.*问题.*"),
                re.compile(r".*为什么.*慢.*"),
                re.compile(r".*如何.*排查.*"),
                re.compile(r".*怎么.*排查.*"),
                re.compile(r".*cpu.*高.*"),
                re.compile(r".*内存.*(高|满|泄漏|不足).*"),
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


@dataclass
class AgentConfig:
    """Configuration for an Agent based on intent recognition result."""
    intent: IntentType
    tools: list = field(default_factory=list)
    prompt_extension: str = ""
    block: bool = False
    block_reply: Optional[str] = None


class IntentGateway:
    """
    Intent recognition gateway.
    Routes queries to appropriate Agent configurations:
    - Classifies intent using rule-based recognizer
    - Selects appropriate tools and prompts per intent type
    - Blocks clearly irrelevant queries to save LLM calls

    Block strategy: only block queries with zero keyword matches.
    A single keyword hit (e.g. "CPU") passes through — the Supervisor
    or Agent will handle the actual routing. This avoids the common
    problem of rule systems being too aggressive and blocking real queries.
    """

    def __init__(self, intent_recognizer: "IntentRecognizer" = None):
        self.recognizer = intent_recognizer or IntentRecognizer()

    def route(self, query: str) -> AgentConfig:
        intent_result = self.recognizer.recognize(query)

        # Only block queries with zero keyword matches (truly irrelevant)
        if intent_result.confidence <= 0.0:
            return AgentConfig(
                intent=intent_result.intent,
                block=True,
                block_reply="我是运维助手，只能回答运维和技术相关的问题。请尝试描述您遇到的技术问题。",
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
