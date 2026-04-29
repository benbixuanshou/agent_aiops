"""Tool mock data validation tests."""

import pytest


class TestK8sTools:
    def test_query_events_production(self):
        from app.tools.k8s_tools import query_k8s_events
        result = query_k8s_events.invoke({"namespace": "production"})
        assert "production" in result
        assert any(kw in result for kw in ["OOM", "CrashLoop", "ImagePull", "Unhealthy"])

    def test_query_events_filtered(self):
        from app.tools.k8s_tools import query_k8s_events
        result = query_k8s_events.invoke({"namespace": "production", "resource": "payment"})
        assert "payment-service" in result

    def test_namespaces(self):
        from app.tools.k8s_tools import get_k8s_namespaces
        result = get_k8s_namespaces.invoke({})
        assert "production" in result


class TestPrometheusTool:
    def test_query_alerts(self):
        from app.tools.prometheus_tool import query_prometheus_alerts
        result = query_prometheus_alerts.invoke({})
        assert isinstance(result, str)


class TestChangeTool:
    def test_query_all_deployments(self):
        from app.tools.change_tools import query_recent_deployments
        result = query_recent_deployments.invoke({"hours": 24})
        assert "payment-service" in result

    def test_query_by_service(self):
        from app.tools.change_tools import query_recent_deployments
        result = query_recent_deployments.invoke({"service": "order-service", "hours": 24})
        assert "order-service" in result
        assert "payment-service" not in result


class TestSLOTool:
    def test_query_slo_status(self):
        from app.tools.slo_tools import query_slo_status
        result = query_slo_status.invoke({"service": ""})
        assert "payment-service" in result
        assert "99.9" in result or "99.87" in result

    def test_query_single_slo(self):
        from app.tools.slo_tools import query_slo_status
        result = query_slo_status.invoke({"service": "payment-service"})
        assert "payment-service" in result
        assert "Error budget" in result


class TestDatetimeTool:
    def test_get_datetime(self):
        from app.tools.datetime_tool import get_current_datetime
        result = get_current_datetime.invoke({})
        assert "202" in result or "CST" in result or "+" in result
