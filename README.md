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

### Install open temeletry

```bash
# Run after make devenv
uv run opentelemetry-bootstrap -a install
```

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

## Running app with Open Telemetry

* Based on Open Telemetry [documentation](https://opentelemetry.io/docs/languages/python/getting-started/) .

```bash
cd open_telemetry_test

# Start Docker

# Copy config yaml to container.
# Download the image from otel and run with the config yaml.
docker run -p 4317:4317 \
  -v ./otel-collector-config.yaml:/etc/otel-collector-config.yaml \
  otel/opentelemetry-collector:latest \
  --config=/etc/otel-collector-config.yaml

# Now run the app with the following command
opentelemetry-instrument --logs_exporter otlp flask run -p 8080

# App can be accessed at http://localhost:8080/rolldice
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