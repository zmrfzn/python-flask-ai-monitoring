export NEW_RELIC_LICENSE_KEY=YOUR_NEW_RELIC_LICENSE_KEY
export OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.nr-data.net
export OTEL_EXPORTER_OTLP_HEADERS="api-key=$NEW_RELIC_LICENSE_KEY"
export OTEL_SERVICE_NAME=bedrock-energy-agent"
python3 main.py
