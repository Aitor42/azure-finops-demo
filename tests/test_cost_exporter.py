"""Tests for cost_exporter.py — token caching, retry logic, and gauge updates."""

import time
from unittest.mock import MagicMock, patch

import pytest

from cost_exporter import SCOPE_API, CostExporter

# ---------------------------------------------------------------------------
# Token caching
# ---------------------------------------------------------------------------


class TestTokenCaching:
    """CostExporter._token() must cache and refresh credentials."""

    @patch("cost_exporter.DefaultAzureCredential")
    def test_fetches_token_on_first_call(self, mock_cred_cls):
        tok = MagicMock(token="first-token", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok

        exporter = CostExporter()
        assert exporter._token() == "first-token"
        mock_cred_cls.return_value.get_token.assert_called_once_with(SCOPE_API)

    @patch("cost_exporter.DefaultAzureCredential")
    def test_returns_cached_token_when_valid(self, mock_cred_cls):
        tok = MagicMock(token="cached", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok

        exporter = CostExporter()
        exporter._token()
        exporter._token()
        assert mock_cred_cls.return_value.get_token.call_count == 1

    @patch("cost_exporter.DefaultAzureCredential")
    def test_refreshes_expired_token(self, mock_cred_cls):
        old = MagicMock(token="old", expires_on=time.time() - 100)
        new = MagicMock(token="new", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.side_effect = [old, new]

        exporter = CostExporter()
        assert exporter._token() == "old"
        assert exporter._token() == "new"
        assert mock_cred_cls.return_value.get_token.call_count == 2


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


class TestRetryLogic:
    """_post_cost_query() must retry 429/5xx with backoff."""

    def _make_exporter(self, mock_cred_cls):
        tok = MagicMock(token="t", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok
        return CostExporter()

    @patch("cost_exporter.DefaultAzureCredential")
    def test_returns_on_first_success(self, mock_cred_cls):
        exporter = self._make_exporter(mock_cred_cls)
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"ok": True}
        exporter._session.post = MagicMock(return_value=resp)

        assert exporter._post_cost_query("https://x", {}) == {"ok": True}
        assert exporter._session.post.call_count == 1

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_retries_on_429_then_succeeds(self, mock_cred_cls, mock_sleep):
        exporter = self._make_exporter(mock_cred_cls)
        r429 = MagicMock(status_code=429)
        r200 = MagicMock(status_code=200)
        r200.json.return_value = {"recovered": True}
        exporter._session.post = MagicMock(side_effect=[r429, r200])

        assert exporter._post_cost_query("https://x", {}) == {"recovered": True}
        assert exporter._session.post.call_count == 2
        mock_sleep.assert_called_once()

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_retries_on_500_then_succeeds(self, mock_cred_cls, mock_sleep):
        exporter = self._make_exporter(mock_cred_cls)
        r500 = MagicMock(status_code=500)
        r200 = MagicMock(status_code=200)
        r200.json.return_value = {"ok": True}
        exporter._session.post = MagicMock(side_effect=[r500, r200])

        assert exporter._post_cost_query("https://x", {}) == {"ok": True}

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_raises_after_max_retries(self, mock_cred_cls, mock_sleep):
        exporter = self._make_exporter(mock_cred_cls)
        resp = MagicMock(status_code=429)
        resp.raise_for_status.side_effect = Exception("429 Too Many Requests")
        exporter._session.post = MagicMock(return_value=resp)

        with pytest.raises(Exception, match="429"):
            exporter._post_cost_query("https://x", {})

    @patch("cost_exporter.DefaultAzureCredential")
    def test_does_not_retry_on_400(self, mock_cred_cls):
        exporter = self._make_exporter(mock_cred_cls)
        resp = MagicMock(status_code=400)
        resp.raise_for_status.side_effect = Exception("400 Bad Request")
        exporter._session.post = MagicMock(return_value=resp)

        with pytest.raises(Exception, match="400"):
            exporter._post_cost_query("https://x", {})
        assert exporter._session.post.call_count == 1


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------


class TestQueryCost:
    """_query_cost() must validate configuration."""

    @patch("cost_exporter.SUBSCRIPTION_ID", None)
    @patch("cost_exporter.DefaultAzureCredential")
    def test_raises_without_subscription_id(self, mock_cred_cls):
        exporter = CostExporter()
        with pytest.raises(RuntimeError, match="AZURE_SUBSCRIPTION_ID"):
            exporter._query_cost("ResourceGroupName")

    @patch("cost_exporter.SUBSCRIPTION_ID", "sub-1234")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_builds_correct_url_and_body(self, mock_cred_cls):
        exporter = CostExporter()
        exporter._post_cost_query = MagicMock(return_value={"ok": True})
        res = exporter._query_cost("ResourceGroupName")
        assert res == {"ok": True}
        exporter._post_cost_query.assert_called_once()
        url, body = exporter._post_cost_query.call_args[0]
        assert "subscriptions/sub-1234/providers/Microsoft.CostManagement" in url
        assert body["dataset"]["grouping"][0]["name"] == "ResourceGroupName"


# ---------------------------------------------------------------------------
# Gauge updates
# ---------------------------------------------------------------------------


class TestGaugeUpdates:
    """_update_labeled_gauge() must set and remove stale labels."""

    @patch("cost_exporter.DefaultAzureCredential")
    def test_sets_gauge_for_each_row(self, mock_cred_cls):
        exporter = CostExporter()
        gauge = MagicMock()
        rows = [["rg-web", 42.5], ["rg-db", 18.3]]

        exporter._update_labeled_gauge(gauge, "resource_group", rows, 0, 1)

        assert gauge.labels.call_count == 2
        gauge.labels.assert_any_call(resource_group="rg-web")
        gauge.labels.assert_any_call(resource_group="rg-db")

    @patch("cost_exporter.DefaultAzureCredential")
    def test_removes_stale_labels(self, mock_cred_cls):
        exporter = CostExporter()
        gauge = MagicMock()

        exporter._update_labeled_gauge(
            gauge, "resource_group", [["rg-a", 1.0], ["rg-b", 2.0]], 0, 1
        )
        exporter._update_labeled_gauge(gauge, "resource_group", [["rg-a", 1.5]], 0, 1)

        gauge.remove.assert_called_once_with("rg-b")

    @patch("cost_exporter.DefaultAzureCredential")
    def test_replaces_none_label_with_unknown(self, mock_cred_cls):
        exporter = CostExporter()
        gauge = MagicMock()

        exporter._update_labeled_gauge(gauge, "resource_group", [[None, 7.0]], 0, 1)

        gauge.labels.assert_called_with(resource_group="unknown")


# ---------------------------------------------------------------------------
# Retry-After header
# ---------------------------------------------------------------------------


class TestRetryAfterHeader:
    """_post_cost_query() must honor the Retry-After header from 429 responses."""

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_uses_retry_after_header_when_present(self, mock_cred_cls, mock_sleep):
        tok = MagicMock(token="t", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok
        exporter = CostExporter()

        r429 = MagicMock(status_code=429, headers={"Retry-After": "30"})
        r200 = MagicMock(status_code=200, headers={})
        r200.json.return_value = {"ok": True}
        exporter._session.post = MagicMock(side_effect=[r429, r200])

        result = exporter._post_cost_query("https://x", {})
        assert result == {"ok": True}
        mock_sleep.assert_called_once_with(30)

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_falls_back_to_backoff_without_retry_after(self, mock_cred_cls, mock_sleep):
        tok = MagicMock(token="t", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok
        exporter = CostExporter()

        r429 = MagicMock(status_code=429, headers={})
        r200 = MagicMock(status_code=200, headers={})
        r200.json.return_value = {"ok": True}
        exporter._session.post = MagicMock(side_effect=[r429, r200])

        exporter._post_cost_query("https://x", {})
        # Exponential backoff: RETRY_BACKOFF_BASE * 2^0 = 2.0
        mock_sleep.assert_called_once_with(2.0)

    @patch("time.sleep")
    @patch("cost_exporter.DefaultAzureCredential")
    def test_invalid_retry_after_falls_back(self, mock_cred_cls, mock_sleep):
        tok = MagicMock(token="t", expires_on=time.time() + 3600)
        mock_cred_cls.return_value.get_token.return_value = tok
        exporter = CostExporter()

        r429 = MagicMock(status_code=429, headers={"Retry-After": "invalid-non-int"})
        r200 = MagicMock(status_code=200, headers={})
        r200.json.return_value = {"ok": True}
        exporter._session.post = MagicMock(side_effect=[r429, r200])

        exporter._post_cost_query("https://x", {})
        mock_sleep.assert_called_once_with(2.0)


# ---------------------------------------------------------------------------
# collect()
# ---------------------------------------------------------------------------


class TestCollect:
    """collect() queries Azure for RG and Service costs and updates gauges."""

    @patch("cost_exporter.SUBSCRIPTION_ID", "sub-1234")
    @patch("cost_exporter.DefaultAzureCredential")
    @patch("cost_exporter.mtd_total")
    @patch("cost_exporter.mtd_by_rg")
    @patch("cost_exporter.mtd_by_service")
    def test_collect_updates_all_metrics(
        self, mock_svc_gauge, mock_rg_gauge, mock_total_gauge, mock_cred_cls
    ):
        exporter = CostExporter()
        rg_response = {
            "properties": {
                "columns": [{"name": "ResourceGroupName"}, {"name": "PreTaxCost"}],
                "rows": [["rg-prod", 50.0], ["rg-dev", 12.5]],
            }
        }
        svc_response = {
            "properties": {
                "columns": [{"name": "ServiceName"}, {"name": "PreTaxCost"}],
                "rows": [["Virtual Machines", 40.0], ["Storage", 22.5]],
            }
        }
        exporter._query_cost = MagicMock(side_effect=[rg_response, svc_response])

        exporter.collect()

        assert exporter.mtd_total == 62.5
        mock_total_gauge.set.assert_called_once_with(62.5)
        assert mock_rg_gauge.labels.call_count == 2
        assert mock_svc_gauge.labels.call_count == 2

    @patch("cost_exporter.SUBSCRIPTION_ID", "sub-1234")
    @patch("cost_exporter.DefaultAzureCredential")
    @patch("cost_exporter.mtd_total")
    @patch("cost_exporter.mtd_by_rg")
    @patch("cost_exporter.mtd_by_service")
    def test_collect_handles_empty_rows(
        self, mock_svc_gauge, mock_rg_gauge, mock_total_gauge, mock_cred_cls
    ):
        exporter = CostExporter()
        rg_empty = {
            "properties": {
                "columns": [{"name": "ResourceGroupName"}, {"name": "PreTaxCost"}],
                "rows": [],
            }
        }
        svc_empty = {
            "properties": {
                "columns": [{"name": "ServiceName"}, {"name": "PreTaxCost"}],
                "rows": [],
            }
        }
        exporter._query_cost = MagicMock(side_effect=[rg_empty, svc_empty])

        exporter.collect()

        assert exporter.mtd_total == 0.0
        mock_total_gauge.set.assert_called_once_with(0.0)


# ---------------------------------------------------------------------------
# main() fail-fast and logging
# ---------------------------------------------------------------------------


class TestMainFailFast:
    """main() must exit immediately when SUBSCRIPTION_ID is not set."""

    @patch("cost_exporter.SUBSCRIPTION_ID", None)
    @patch("cost_exporter._configure_logging")
    def test_exits_1_without_subscription_id(self, mock_logging):
        from cost_exporter import main

        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 1

    def test_configure_logging(self):
        from cost_exporter import _configure_logging

        _configure_logging()

    @patch("cost_exporter.SUBSCRIPTION_ID", "sub-1234")
    @patch("cost_exporter.start_http_server")
    @patch("cost_exporter.CostExporter")
    @patch("cost_exporter.time.sleep", side_effect=KeyboardInterrupt)
    def test_main_runs_cycle_and_handles_exception(self, mock_sleep, mock_exporter_cls, mock_http):
        mock_exporter = MagicMock()
        mock_exporter_cls.return_value = mock_exporter
        mock_exporter.collect.side_effect = Exception("error")

        from cost_exporter import main

        with pytest.raises(KeyboardInterrupt):
            main()

        assert mock_http.called
        assert mock_exporter.collect.called
