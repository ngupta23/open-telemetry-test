import time
from threading import Lock

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from prometheus_client import start_http_server

from open_telemetry_test.predictive.predictive_common import collect_vibration_data

# Start Prometheus server on port 8000
start_http_server(port=8000)

# Initialize OpenTelemetry
reader = PrometheusMetricReader()
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("vibration.meter")

# Thread-safe storage for vibration value
current_vibration = 0.0
vibration_lock = Lock()


# Create an ObservableGauge with callback
def vibration_callback(options):
    return [
        metrics.Observation(current_vibration, attributes={"machine_id": "machine_1"})
    ]


vibration_gauge = meter.create_observable_gauge(
    name="machine_vibration_acceleration",
    callbacks=[vibration_callback],
    # unit="g",
    description="Machine vibration acceleration in g",
)

if __name__ == "__main__":
    while True:
        value = collect_vibration_data()
        print(f"Vibration data collected: {value}")
        with vibration_lock:
            current_vibration = value
        time.sleep(5)
