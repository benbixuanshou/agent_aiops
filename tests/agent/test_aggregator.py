"""AlertAggregator unit tests."""

import pytest
from app.agent.alert_aggregator import AlertAggregator, Incident


class TestAlertAggregator:
    def test_empty_returns_empty(self):
        agg = AlertAggregator()
        assert agg.aggregate([]) == []

    def test_single_alert_creates_incident(self, mock_alerts):
        agg = AlertAggregator()
        incidents = agg.aggregate([mock_alerts[0]])
        assert len(incidents) == 1
        assert incidents[0].severity == "P1"

    def test_related_alerts_merge(self, mock_alerts):
        """Two alerts for same service should be grouped."""
        agg = AlertAggregator()
        incidents = agg.aggregate([mock_alerts[0], mock_alerts[1]])
        assert len(incidents) == 1
        assert len(incidents[0].alerts) == 2

    def test_different_services_separate(self, mock_alerts):
        """Alerts from different services should be separate incidents."""
        agg = AlertAggregator()
        incidents = agg.aggregate([mock_alerts[0], mock_alerts[2]])
        assert len(incidents) == 2

    def test_critical_priority(self, mock_alerts):
        agg = AlertAggregator()
        incidents = agg.aggregate([mock_alerts[2]])  # critical
        assert incidents[0].severity == "P0"

    def test_p0_sorts_first(self, mock_alerts):
        agg = AlertAggregator()
        incidents = agg.aggregate([mock_alerts[0], mock_alerts[2]])
        assert incidents[0].severity == "P0"
