devenv:
	@echo "Creating development environment..."
	uv sync --frozen
	uv run pre-commit install

split-tests:
	@echo "Running tests in parallel for group $${GROUP:-1} of $${SPLITS:-4}..."
	COVERAGE_FILE=$${COVERAGE_FILE:-coverage.default} \
	uv run pytest --splits $${SPLITS:-4} --group $${GROUP:-1}

setup-prometheus:
	sudo apt update
	cd open_telemetry_test/prometheus && \
	wget https://github.com/prometheus/prometheus/releases/download/v3.3.0/prometheus-3.3.0.linux-amd64.tar.gz && \
	tar xvfz prometheus-*.tar.gz && \
	rm prometheus-*.tar.gz

start-prometheus:
	cd open_telemetry_test/prometheus && \
	prometheus-3.3.0.linux-amd64/prometheus --config.file=prometheus_predictive.yaml

start-otel-common-docker:
	cd open_telemetry_test/otel_common && \
	docker run --rm \
		--env-file ../../.env \
		-p 4317:4317 -p 4318:4318 -p 8000:8000 \
   		-v ./otel_common_collector_config.yaml:/etc/otelcol-contrib/config.yaml \
   		otel/opentelemetry-collector-contrib:latest \
   		--config /etc/otelcol-contrib/config.yaml

supabase-detect-anomalies:
	cd open_telemetry_test/supabase && \
	uv run python performance.py

supabase-anomaly-dashboard:
	cd open_telemetry_test/supabase && \
	uv run python dashboard.py
