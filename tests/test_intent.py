"""Intent recognition tests."""

from app.rag.intent import IntentRecognizer, IntentType


def test_troubleshooting_cpu():
    r = IntentRecognizer()
    result = r.recognize("CPU 使用率过高怎么排查")
    assert result.intent == IntentType.TROUBLESHOOTING

def test_troubleshooting_error():
    r = IntentRecognizer()
    result = r.recognize("order-service 报错了 500 Internal Server Error")
    assert result.intent == IntentType.TROUBLESHOOTING

def test_technical_question():
    r = IntentRecognizer()
    result = r.recognize("Redis 怎么配置持久化")
    assert result.intent == IntentType.TECHNICAL_QUESTION

def test_configuration():
    r = IntentRecognizer()
    result = r.recognize("Docker 怎么部署到生产环境")
    assert result.intent == IntentType.CONFIGURATION

def test_empty_query():
    r = IntentRecognizer()
    result = r.recognize("")
    assert result.intent == IntentType.GENERAL_QUESTION
    assert result.confidence == 0.0

def test_general_fallback():
    r = IntentRecognizer()
    result = r.recognize("今天天气怎么样")
    assert result.intent == IntentType.GENERAL_QUESTION
