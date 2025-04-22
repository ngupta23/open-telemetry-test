import pandas as pd
from dotenv import load_dotenv
from nixtla import NixtlaClient
from opentelemetry import metrics, trace

load_dotenv()

# Acquire a tracer
tracer = trace.get_tracer("oad.tracer")
# Acquire a meter.
meter = metrics.get_meter("oad.meter")

# Now create a counter instrument to make measurements with
anomaly_counter_per_id = meter.create_counter(
    "anomaly.unique_id",
    description="The number of anomalies detected for each unique_id",
)

anomaly_counter_overall = meter.create_counter(
    "anomaly.all",
    description="The number of anomalies detected overall",
)

nixtla_client = NixtlaClient(
    # defaults to os.environ.get("NIXTLA_API_KEY")
    # api_key = "",
)


df = pd.read_csv(
    "https://datasets-nixtla.s3.us-east-1.amazonaws.com/SMD_test.csv",
    parse_dates=["ts"],
)
print(df.head())

with tracer.start_as_current_span("detect_anomaly") as detect_anomaly:
    anomaly_online = nixtla_client.detect_anomalies_online(
        df[["ts", "y", "unique_id"]],
        time_col="ts",
        target_col="y",
        freq="h",
        h=24,
        level=95,
        detection_size=475,
        threshold_method="univariate",  # Specify the threshold_method as 'univariate'
    )

    current_time = df["ts"].max().isoformat()
    # current_time = int(current_time.timestamp())
    detect_anomaly.set_attribute("current_time", current_time)

    # Track counts of anomalies per unique_id
    anomaly_counts = anomaly_online.query("anomaly == True").groupby("unique_id").size()

    # Emit the metrics
    for unique_id, count in anomaly_counts.items():
        anomaly_counter_per_id.add(
            # convert numpy.int64 to plain int
            int(count),
            {"unique_id": str(unique_id)},
        )

    # convert numpy.int64 to plain int
    total_anomalies = int(anomaly_counts.sum())
    anomaly_counter_overall.add(total_anomalies, {"unique_id": "ALL"})
