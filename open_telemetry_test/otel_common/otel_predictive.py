import time
from threading import Lock

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

from open_telemetry_test.prometheus.predictive_common import collect_vibration_data

TIME_SECS = 5

# Initialize OTLP exporter to send to local collector
otlp_exporter = OTLPMetricExporter(endpoint="localhost:4317", insecure=True)

# Export metrics every 5 second (Default is 60 seconds)
# Set this frequency to be higher than the frequency of the tools used to
# collect the metrics. Example, prometheus may read the metrics every 15 seconds,
# so if we leave this at 60 seconds, we will collect the same metric value 4 times.
reader = PeriodicExportingMetricReader(
    otlp_exporter, export_interval_millis=TIME_SECS * 1000
)
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("vibration.meter")

current_vibration = 0.0
vibration_lock = Lock()


def vibration_callback(options):
    return [
        metrics.Observation(current_vibration, attributes={"machine_id": "machine_1"})
    ]


vibration_gauge = meter.create_observable_gauge(
    name="machine_vibration_acceleration",
    callbacks=[vibration_callback],
    description="Machine vibration acceleration in g",
)

if __name__ == "__main__":
    while True:
        value = collect_vibration_data()
        print(f"Vibration data collected: {value}")
        with vibration_lock:
            current_vibration = value
        time.sleep(TIME_SECS)
