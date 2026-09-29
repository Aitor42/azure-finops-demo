#!/usr/bin/env python3
"""Export Azure actual cost (month-to-date) to Prometheus.

Exposes Prometheus-format metrics on :9099 (configurable) so Prometheus can
scrape them and Grafana can graph them. Maps to the FinOps "Cost reporting"
capability.

Requirements:
  - "Cost Management Reader" role on the subscription (or Contributor/Owner).
  - Env vars: AZURE_SUBSCRIPTION_ID (required). Optional: COST_EXPORTER_PORT,
    COST_EXPORTER_BIND, COST_EXPORTER_INTERVAL.

Usage:
  AZURE_SUBSCRIPTION_ID=<sub-id> python3 cost_exporter.py
"""

import logging
import os
import sys
import time
from typing import Any, cast

import requests
from azure.identity import DefaultAzureCredential
from prometheus_client import Gauge, start_http_server

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (from environment variables)
# ---------------------------------------------------------------------------
SUBSCRIPTION_ID: str | None = os.environ.get("AZURE_SUBSCRIPTION_ID")
PORT: int = int(os.environ.get("COST_EXPORTER_PORT", "9099"))
# Bind to loopback by default so cost metrics aren't exposed on the LAN.
BIND_ADDR: str = os.environ.get("COST_EXPORTER_BIND", "127.0.0.1")
INTERVAL_SECONDS: int = int(os.environ.get("COST_EXPORTER_INTERVAL", "3600"))

# ---------------------------------------------------------------------------
# Azure Cost Management API constants
# ---------------------------------------------------------------------------
API_VERSION: str = "2023-11-01"
SCOPE_API: str = "https://management.azure.com/.default"
REQUEST_TIMEOUT: int = 30
TOKEN_REFRESH_MARGIN: int = 300  # Refresh token 5 min before expiry.
MAX_RETRIES: int = 5
RETRY_BACKOFF_BASE: float = 2.0  # Seconds; doubles each attempt.

# ---------------------------------------------------------------------------
# Prometheus gauges
# ---------------------------------------------------------------------------
mtd_total = Gauge(
    "azure_cost_mtd_total_eur",
    "Actual month-to-date cost in EUR (subscription)",
)
mtd_by_rg = Gauge(
    "azure_cost_mtd_by_resource_group_eur",
    "MTD cost by resource group",
    ["resource_group"],
)
mtd_by_service = Gauge(
    "azure_cost_mtd_by_service_eur",
    "MTD cost by service",
    ["service"],
)


class CostExporter:
    """Collects Azure cost data and exposes it as Prometheus metrics.

    Encapsulates the credential cache, HTTP session, and label-tracking state
    so nothing leaks into module-level mutable globals.
    """

    def __init__(self) -> None:
        self._credential = DefaultAzureCredential()
        self._session = requests.Session()
        self._cached_token: str | None = None
        self._cached_token_expiry: float = 0.0
        self._seen_labels: dict[str, set[str]] = {
            "resource_group": set(),
            "service": set(),
        }
        self.mtd_total: float = 0.0

    # -- Token management ---------------------------------------------------

    def _token(self) -> str:
        """Return a cached bearer token, refreshing it when close to expiry."""
        now = time.time()
        if self._cached_token is None or now > self._cached_token_expiry:
            cred = self._credential.get_token(SCOPE_API)
            self._cached_token = cred.token
            self._cached_token_expiry = cred.expires_on - TOKEN_REFRESH_MARGIN
        return self._cached_token

    # -- Azure Cost Management queries --------------------------------------

    def _post_cost_query(self, url: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST a cost query with retry on 429/5xx and exponential backoff.

        Honors the ``Retry-After`` header from 429 responses when present;
        falls back to exponential backoff otherwise.
        """
        for attempt in range(MAX_RETRIES + 1):
            resp = self._session.post(
                url,
                json=body,
                headers={"Authorization": f"Bearer {self._token()}"},
                timeout=REQUEST_TIMEOUT,
            )
            is_retriable = resp.status_code == 429 or resp.status_code >= 500
            if not is_retriable or attempt == MAX_RETRIES:
                resp.raise_for_status()
                return cast("dict[str, Any]", resp.json())
            # Honor Retry-After header if present; fall back to exponential backoff.
            wait = RETRY_BACKOFF_BASE * (2**attempt)
            try:
                retry_after = resp.headers.get("Retry-After")
                if retry_after is not None:
                    parsed = int(retry_after)
                    if parsed > 0:
                        wait = parsed
            except (AttributeError, ValueError, TypeError):
                pass  # Fall through to exponential backoff.
            logger.warning(
                "Retriable HTTP %d on attempt %d/%d — retrying in %.1fs",
                resp.status_code,
                attempt + 1,
                MAX_RETRIES,
                wait,
            )
            time.sleep(wait)
        # Unreachable, but keeps mypy happy.
        raise RuntimeError("Exceeded maximum retries")  # pragma: no cover

    def _query_cost(self, group_by: str) -> dict[str, Any]:
        """Query the Cost Management API grouped by *group_by* dimension."""
        if not SUBSCRIPTION_ID:
            raise RuntimeError("Define AZURE_SUBSCRIPTION_ID")

        scope = f"/subscriptions/{SUBSCRIPTION_ID}"
        url = (
            f"https://management.azure.com{scope}/providers/"
            f"Microsoft.CostManagement/query?api-version={API_VERSION}"
        )
        body: dict[str, Any] = {
            "type": "Usage",
            "timeframe": "MonthToDate",
            "dataset": {
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "PreTaxCost", "function": "Sum"},
                },
                "grouping": [{"type": "Dimension", "name": group_by}],
            },
        }
        return self._post_cost_query(url, body)

    # -- Gauge helpers ------------------------------------------------------

    def _update_labeled_gauge(
        self,
        gauge: Gauge,
        label: str,
        rows: list[list[Any]],
        label_index: int,
        cost_index: int,
    ) -> None:
        """Set the gauge for every row and remove labels that no longer report."""
        current = {row[label_index] or "unknown" for row in rows}
        for stale in self._seen_labels[label] - current:
            gauge.remove(stale)
        self._seen_labels[label] = current

        for row in rows:
            value = row[label_index] or "unknown"
            gauge.labels(**{label: value}).set(float(row[cost_index] or 0.0))

    # -- Public API ---------------------------------------------------------

    def collect(self) -> None:
        """Fetch cost data from Azure and update all Prometheus gauges.

        Both API queries run before any gauge is touched, so a failure in the
        second query does not leave gauges in an inconsistent half-updated state.
        """
        # Fetch all data first — avoids partial updates on error.
        rg_data = self._query_cost("ResourceGroupName")
        svc_data = self._query_cost("ServiceName")

        # By resource group
        props = rg_data["properties"]
        cols = [c["name"] for c in props["columns"]]
        i_group = cols.index("ResourceGroupName")
        i_cost = cols.index("PreTaxCost")
        rg_rows: list[list[Any]] = props.get("rows", [])
        self._update_labeled_gauge(mtd_by_rg, "resource_group", rg_rows, i_group, i_cost)
        total = sum(float(r[i_cost] or 0.0) for r in rg_rows)

        # By service
        cols = [c["name"] for c in svc_data["properties"]["columns"]]
        i_service = cols.index("ServiceName")
        i_cost = cols.index("PreTaxCost")
        svc_rows: list[list[Any]] = svc_data["properties"].get("rows", [])
        self._update_labeled_gauge(mtd_by_service, "service", svc_rows, i_service, i_cost)

        self.mtd_total = total
        mtd_total.set(self.mtd_total)


def _configure_logging() -> None:
    """Set up structured logging to stderr."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stderr,
    )


def main() -> None:
    """Entry point: start the HTTP server and poll Azure cost data forever."""
    _configure_logging()

    if not SUBSCRIPTION_ID:
        logger.error("AZURE_SUBSCRIPTION_ID environment variable is required")
        sys.exit(1)

    exporter = CostExporter()
    start_http_server(PORT, addr=BIND_ADDR)
    logger.info("Listening on %s:%d (subscription=%s)", BIND_ADDR, PORT, SUBSCRIPTION_ID)

    while True:
        try:
            exporter.collect()
            logger.info("Metrics updated: %.2f EUR MTD", exporter.mtd_total)
        except Exception:
            logger.exception("Collection cycle failed")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
