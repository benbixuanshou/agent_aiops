"""Shared test fixtures."""

import pytest


@pytest.fixture
def mock_alerts():
    return [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighCPUUsage",
                "severity": "warning",
                "service": "payment-service",
                "namespace": "production",
            },
            "annotations": {"summary": "CPU usage above 80%"},
            "startsAt": "2026-04-28T10:00:00Z",
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "HighMemoryUsage",
                "severity": "warning",
                "service": "payment-service",
                "namespace": "production",
            },
            "annotations": {"summary": "Memory usage above 85%"},
            "startsAt": "2026-04-28T10:01:00Z",
        },
        {
            "status": "firing",
            "labels": {
                "alertname": "ServiceUnavailable",
                "severity": "critical",
                "service": "order-service",
                "namespace": "production",
            },
            "annotations": {"summary": "Service is down"},
            "startsAt": "2026-04-28T10:02:00Z",
        },
    ]
