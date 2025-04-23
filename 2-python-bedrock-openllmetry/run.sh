#export NEW_RELIC_LICENSE_KEY=MY_NEW_RELIC_LICENSE_KEY
export TRACELOOP_BASE_URL=https://otlp.nr-data.net:443
export TRACELOOP_HEADERS="api-key=${NEW_RELIC_LICENSE_KEY}"

flask --app leveltwo.py run --host 0.0.0.0 --port=5002