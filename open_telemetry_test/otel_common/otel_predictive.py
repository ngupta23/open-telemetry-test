import time
from threading import Lock

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from open_telemetry_test.prometheus.predictive_common import collect_vibration_data

TIME_SECS = 5

# -----------------------------------------------------------------------------#
# Metrics
# -----------------------------------------------------------------------------#

# Initialize OTLP Metric exporter to send to local collector
otlp_metric_exporter = OTLPMetricExporter(endpoint="localhost:4317", insecure=True)

# Export metrics every 5 second (Default is 60 seconds)
# Set this frequency to be higher than the frequency of the tools used to
# collect the metrics. Example, prometheus may read the metrics every 15 seconds,
# so if we leave this at 60 seconds, we will collect the same metric value 4 times.
reader = PeriodicExportingMetricReader(
    otlp_metric_exporter, export_interval_millis=TIME_SECS * 1000
)
provider = MeterProvider(metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("vibration.meter")

# -----------------------------------------------------------------------------#
# Span
# -----------------------------------------------------------------------------#

trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer("vibration.tracer")

# Initialize OTLP Span exporter to send to local collector
otlp_span_exporter = OTLPSpanExporter(endpoint="localhost:4317", insecure=True)

trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_span_exporter))

METRIC_NAME = "machine_vibration_acceleration"

current_vibration = 0.0
vibration_lock = Lock()


def vibration_callback(options):
    return [
        metrics.Observation(current_vibration, attributes={"machine_id": "machine_1"})
    ]


vibration_gauge = meter.create_observable_gauge(
    name=METRIC_NAME,
    callbacks=[vibration_callback],
    description="Machine vibration acceleration in g",
)

if __name__ == "__main__":
    while True:
        with tracer.start_as_current_span("vibration-sample") as span:
            value = collect_vibration_data()
            print(f"Vibration data collected: {value}")

            # Add value to the span (for Sentry) as we can not export metrics to Sentry
            span.set_attribute("machine_id", "machine_1")
            span.set_attribute(METRIC_NAME, value)

            # Update metric value (for tools like Prometheus)
            with vibration_lock:
                current_vibration = value
        time.sleep(TIME_SECS)
