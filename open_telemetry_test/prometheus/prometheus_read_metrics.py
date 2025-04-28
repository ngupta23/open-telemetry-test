from datetime import datetime, timedelta

import pandas as pd
from prometheus_api_client import PrometheusConnect

# Connect to your Prometheus server
prom = PrometheusConnect(url="http://localhost:9090", disable_ssl=True)

# Define time range
end_time = datetime.now()
start_time = end_time - timedelta(minutes=10)


query = 'machine_vibration_acceleration{machine_id="machine_1"}'


def get_metric(query: str) -> pd.DataFrame:
    """Fetch metric data over the time range

    Parameters
    ----------
    query : str
        PromQL query to fetch the metric data

    Returns
    -------
    pd.DataFrame
        The metric data in a DataFrame format (columns: ds, metric_name)
    """
    result = prom.get_metric_range_data(
        query,
        start_time=start_time,
        end_time=end_time,
        chunk_size=timedelta(minutes=10),
    )

    metric_name = result[0].get("metric").get("__name__")
    metric = pd.DataFrame(result[0].get("values"), columns=["ds", metric_name])
    metric["ds"] = pd.to_datetime(metric["ds"], unit="s")
    return metric


def get_average_metric(query: str, step: str) -> pd.DataFrame:
    """Fetch the average for the last N seconds (from query), at `step` intervals

    Parameters
    ----------
    query : str
        PromQL query to fetch the average metric data
    step : str
        The time interval between data points, e.g. 60s, 1m, etc.

    Returns
    -------
    pd.DataFrame
        The average metric data in a DataFrame format (columns: ds, avg)
    """
    result = prom.custom_query_range(
        query=query, start_time=start_time, end_time=end_time, step=step
    )
    metric_avg = pd.DataFrame(result[0].get("values"), columns=["ds", "avg"])
    metric_avg["ds"] = pd.to_datetime(metric_avg["ds"], unit="s")
    return metric_avg


# PromQL query for your metric (raw metrics)
query = 'machine_vibration_acceleration{machine_id="machine_1"}'
metric = get_metric(query)
print(metric)

# Average for the last 30s
# PromQL query for your metric (average over time)
query = 'avg_over_time(machine_vibration_acceleration{machine_id="machine_1"}[30s])'
metric_avg = get_average_metric(query, step="60s")
print(metric_avg)
