# Containerized cost exporter — exposes Azure cost metrics as Prometheus gauges.
#
# Required environment variables:
#   AZURE_SUBSCRIPTION_ID   Azure subscription to query costs for
#
# Optional:
#   COST_EXPORTER_PORT      Metrics port (default: 9099)
#   COST_EXPORTER_INTERVAL  Seconds between Azure API polls (default: 3600)
#
# Azure credentials: mount a service principal or use workload identity.
# Example:
#   docker run -e AZURE_SUBSCRIPTION_ID=<sub-id> \
#              -e AZURE_CLIENT_ID=<id> -e AZURE_CLIENT_SECRET=<secret> \
#              -e AZURE_TENANT_ID=<tenant> \
#              -p 9099:9099 cost-exporter

FROM python:3.12-slim

WORKDIR /app

COPY scripts/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY scripts/cost_exporter.py .

# In a container, bind to all interfaces (the host/orchestrator controls exposure).
ENV COST_EXPORTER_BIND=0.0.0.0
EXPOSE 9099

# Run as non-root for security.
RUN useradd --create-home --no-log-init appuser
USER appuser

HEALTHCHECK --interval=60s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:9099/metrics')" || exit 1

ENTRYPOINT ["python3", "cost_exporter.py"]
