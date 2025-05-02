"""
Script uses Prometheus Client directly to scrape metrics (no OTEL involved).
"""

import time

from prometheus_client import Gauge, start_http_server

from open_telemetry_test.predictive.predictive_common import collect_vibration_data

# Create a Gauge metric for vibration
vibration_gauge = Gauge(
    "machine_vibration_acceleration",  # metric name
    "Machine vibration acceleration in g",
    [
        "machine_id"
    ],  # labels to use, e.g. machine_id="machine_1", "machine_id=machine_2", etc
)

if __name__ == "__main__":
    # Start HTTP server on port 8000
    # Mention this port in the YAML file to catch these metrics
    start_http_server(8000)
    machine_id = "machine_1"
    while True:
        value = collect_vibration_data()
        print(f"Vibration data collected: {value}")
        vibration_gauge.labels(machine_id=machine_id).set(value)
        time.sleep(5)  # Spit out the metric every 5 seconds
