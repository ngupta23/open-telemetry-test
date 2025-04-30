[![lint](https://github.com/ngupta23/open_telemetry_test/actions/workflows/lint.yaml/badge.svg)](https://github.com/ngupta23/open_telemetry_test/actions/workflows/lint.yaml)
[![CI](https://github.com/ngupta23/open_telemetry_test/actions/workflows/ci.yaml/badge.svg)](https://github.com/ngupta23/open_telemetry_test/actions/workflows/ci.yaml)

# open_telemetry_test
A template for testing Open Telemetry functionality.

## 🛠️ Create the Development Environment & 🔧 Install Pre-commit Hooks

* Pre-commit hooks help maintain code quality by running checks before commits.
* Update the .pre-commit-config.yaml if needed, then run the following command
  * `make devenv`
  * This will do both of these steps - create the dev env and install pre-commit.

```bash
# Install uv
pip install uv

# Create and activate a virtual environment
uv venv --python 3.10
source .venv/bin/activate

# # Initialize uv. NOTE: The following may not have an impact since we are already
# # adding a custom project.toml to this repository
# uv init

make devenv
```

### Install open telemetry

```bash
# Run after make devenv
uv run opentelemetry-bootstrap -a install
```

### Install prometheus

```bash
# Run after make devenv
make setup-prometheus
```

### Add the NIXTLA API KEY

1. Copy the `.env.example` file and rename it to `.env`.
2. Fill the values for the various env variables. These are necessary for the various scripts to run.


## 🔄 Update Dependencies

If you want to add or update dependencies, you can do so using the `uv` command. This will update the `pyproject.toml` file and the lock file.

```bash
# Update dependencies for production
uv add <prod_lib>

# To add to dev dependency group
# https://docs.astral.sh/uv/concepts/projects/dependencies/#development-dependencies
uv add --dev <dev_lib>

# update the lock file
uv lock
```

## Running basic app with Open Telemetry

* Based on Open Telemetry [documentation](https://opentelemetry.io/docs/languages/python/getting-started/) .

```bash
cd open_telemetry_test

# Step 1: Start Docker

# Step 2: Start the collector
# Copy config yaml to container, download the image from otel & run with the config.
docker run -p 4317:4317 \
  -v ./otel-collector-config.yaml:/etc/otel-collector-config.yaml \
  otel/opentelemetry-collector:latest \
  --config=/etc/otel-collector-config.yaml

# Step 3A: Now run the app with the following command
# App can be accessed at http://localhost:8080/rolldice
opentelemetry-instrument --logs_exporter otlp flask run -p 8080

# Step 3B: Alternately, run the following python script
opentelemetry-instrument --logs_exporter otlp python online_anomaly_detection.py
```

## Collecting metrics with Prometheus

Make sure that the prometheus server is running and that the config file is set up correctly. The config file is in the `prometheus` folder.

### Step 1: Start the prometheus server

```bash

# This used prometheus_predictive.yaml as the config file
# which reads the metrics from http://localhost:8000/metrics
make start-prometheus
```

### Step 2: Run the script to collect metrics

* These scripts will expose the metrics at http://localhost:8000/metrics which will be read by prometheus (see config in prometheus_predictive.yaml).

We have 2 options

```bash
# Option 1: Use Prometheus native SDK (tool specific)
uv run python open_telemetry_test/prometheus/prometheus_predictive.py

# Option 2: Use Open Telemetry SDK (preferred since it can export to other tools as well)
# This still mixes the prometheus SDK with Open Telemetry SDK in code, hence it is not the best option.
uv run python open_telemetry_test/prometheus/prometheus_predictive_otel.py
```

### Step 3: Read Metrics

You can query the metrics using PromQL by running the following script

```bash
uv run python open_telemetry_test/prometheus/prometheus_read_metrics.py
```


## Using OTEL as a common collector (PREFERRED)

* This is the preferred method since we use OTEL as a common collector and then export the data to other tools.


### Step 1: Start Prometheus

* With custom settings (e.g. reading metrics every 15 seconds instead of the default 1 min)
  - This starts prometheus at http://localhost:9090/ where you can query the metrics
  - It will look for localhost:8000/metrics to scrape metrics

```bash
make start-prometheus
```

### Step 2: Start docker


### Step 3: Run the docker image with ports forwarded
  * 8000 is for Prometheus to parse metrics
  * rest are for OTEL

```bash
make start-otel-common-docker
```

### Step 4: Start collecting metrics using OTEL

* This will also expose localhost:8000/metrics since we started docker with a config to indicate this endpoint
  - NOTE: This may take some time to show the metrics - it is not instantaneous.

```bash
uv run python open_telemetry_test/otel_common/otel_predictive.py
```

### Step 5: Programmatically pull metrics

```bash
uv run python open_telemetry_test/prometheus/prometheus_read_metrics.py --metric_prefix=otel_
```


## 🏃 Run tests

* pytest settings are in the `pyproject.toml` file so everything does not need to be specified in the command line.
* The tests are split and run in parallel to speed up the CI.
* Some tests can be flaky, for example when doing live testing with other systems without mocking. This issue can be overcome with the rerun option which is also enabled.
* Make sure that the tests are passing and that they pass the coverage requirement.

```bash
# to run all tests
uv run pytest

# to run specific splits of the tests (mostly useful for CI, not standalone).
make split-tests SPLITS=4 GROUP=2
```