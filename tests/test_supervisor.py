"""Supervisor routing tests."""

import pytest


class TestGatewayRoute:
    def test_block_empty_query(self):
        from app.rag.intent import IntentGateway, IntentType
        gw = IntentGateway()
        config = gw.route("")
        assert config.block is True

    def test_block_gibberish(self):
        from app.rag.intent import IntentGateway
        gw = IntentGateway()
        config = gw.route("asdf")
        assert config.block is True

    def test_pass_technical(self):
        from app.rag.intent import IntentGateway, IntentType
        gw = IntentGateway()
        config = gw.route("CPU 使用率过高怎么排查")
        assert config.block is False
        assert config.intent in (IntentType.TROUBLESHOOTING, IntentType.GENERAL_QUESTION)

    def test_pass_config(self):
        from app.rag.intent import IntentGateway, IntentType
        gw = IntentGateway()
        config = gw.route("Redis 怎么配置持久化")
        assert config.block is False

    def test_weak_relevance(self):
        from app.rag.intent import IntentGateway
        gw = IntentGateway()
        config = gw.route("今天天气怎么样")
        assert config.block is False
        assert config.weak_relevance is True

    def test_strong_vs_weak(self):
        from app.rag.intent import IntentGateway
        gw = IntentGateway()
        strong = gw.route("CPU 过高怎么排查")
        weak = gw.route("1+1等于多少")
        # strong should not be weak_relevance
        assert not strong.weak_relevance
        # 1+1 is >6 chars, passes relevance fallback, but has no intent match → weak
        assert weak.block is False  # passes via length fallback

    def test_relevance_counts(self):
        from app.rag.intent import IntentRecognizer
        r = IntentRecognizer()
        assert r.check_relevance("数据库连接池") > 0
        assert r.check_relevance("今天天气") == 0  # no tech keywords, but 4 chars < 6 → 0
        assert r.check_relevance("今天天气怎么样啊") > 0  # 7 chars ≥ 6 → 1


class TestTemplateSeverity:
    def test_all_templates_have_severity(self):
        from app.agent.task_templates import TASK_TEMPLATES, SEVERITY
        for key, tmpl in TASK_TEMPLATES.items():
            assert tmpl.get("severity") in ("P0", "P1", "P2"), f"{key}: missing valid severity"
            assert tmpl.get("label"), f"{key}: missing label"

    def test_severity_structure(self):
        from app.agent.task_templates import SEVERITY
        for level in ("P0", "P1", "P2"):
            assert level in SEVERITY
            assert "label" in SEVERITY[level]
            assert "color" in SEVERITY[level]
