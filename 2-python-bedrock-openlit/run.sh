#export NEW_RELIC_LICENSE_KEY=MY_NEW_RELIC_LICENSE_KEY
export OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp.nr-data.net:443
export OTEL_EXPORTER_OTLP_HEADERS="api-key=${NEW_RELIC_LICENSE_KEY}"

flask --app leveltwo.py run --host 0.0.0.0 --port=5002