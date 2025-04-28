devenv:
	@echo "Creating development environment..."
	uv sync --extra dev --frozen
	uv run pre-commit install

split-tests:
	@echo "Running tests in parallel for group $${GROUP:-1} of $${SPLITS:-4}..."
	COVERAGE_FILE=$${COVERAGE_FILE:-coverage.default} \
	uv run pytest --splits $${SPLITS:-4} --group $${GROUP:-1}

setup-prometheus:
	sudo apt update
	cd open_telemetry_test/prometheus && \
	wget https://github.com/prometheus/prometheus/releases/download/v3.3.0/prometheus-3.3.0.linux-amd64.tar.gz && \
	tar xvfz prometheus-*.tar.gz

start-prometheus:
	cd open_telemetry_test/prometheus && \
	prometheus-3.3.0.linux-amd64/prometheus --config.file=prometheus_predictive.yaml