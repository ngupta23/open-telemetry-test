import os

import pandas as pd
import requests  # type: ignore[import]
import resend
from dotenv import load_dotenv
from nixtla import NixtlaClient
from utilsforecast.preprocessing import fill_gaps

load_dotenv()

nixtla_client = NixtlaClient(
    # defaults to os.environ.get("NIXTLA_API_KEY")
    # api_key = "",
)
resend.api_key = os.getenv("RESEND_API_KEY")

# Sentry Settings ----
SENTRY_AUTH_TOKEN = os.getenv("SENTRY_AUTH_TOKEN")
ORG_SLUG = os.getenv("SENTRY_ORG_SLUG")
PROJECT_SLUG = os.getenv("SENTRY_PROJECT_SLUG")

# TIMEGPT Settings ----
FREQ = "5min"
TIME_COL = "dateCreated"
ID_COL = "metadata.type"
TARGET_COL = "event_count"

current_time = pd.Timestamp.now(tz="UTC").floor(FREQ).strftime("%Y-%m-%d %H:%M")


def get_sentry_events_data() -> pd.DataFrame:
    """Get the sentry events data from the Sentry API.

    Refer to https://github.com/ngupta23/Data-Science-Knowlege-Base/issues/212
    for details on various endpoints and their usage.

    Returns
    -------
    pd.DataFrame
        Sentry events data
    """
    headers = {
        "Authorization": f"Bearer {SENTRY_AUTH_TOKEN}",
        "Content-Type": "application/json",
    }

    # category = error, span_indexed, transaction_indexed, span, transaction
    # url = (
    #     f"https://sentry.io/api/0/organizations/{ORG_SLUG}/stats_v2/"
    #     "?query="
    #     f"project:{PROJECT_SLUG}"
    #     "&interval=5m"
    #     "&statsPeriod=1d"
    #     "&groupBy=category"
    #     "&category=error"
    #     "&field=sum(quantity)"
    # )

    # Does not take interval as a parameter (returns single average value)
    url = (
        f"https://sentry.io/api/0/organizations/{ORG_SLUG}/events/"
        "?query="
        f"project:{PROJECT_SLUG}"
        "&transaction=/forecast"
        "&statsPeriod=1d"
        "&field=avg(transaction.duration)"
    )
    response = requests.get(url, headers=headers)
    print(response.json().get("data"))

    # Returns the average transaction duration for the last 24 hours in 5 minute
    # intervals. Average value is returned as a key called "count"
    url = (
        f"https://sentry.io/api/0/organizations/{ORG_SLUG}/events-stats/"
        "?query="
        f"project:{PROJECT_SLUG}"
        "&transaction=/forecast"
        "&interval=5m"
        "&statsPeriod=1d"
        "&yAxis=avg(transaction.duration)"
    )
    response = requests.get(url, headers=headers)
    print(response.json().get("data"))

    # Process events data ----
    events = pd.DataFrame(
        {
            TIME_COL: response.json().get("intervals"),
            TARGET_COL: response.json().get("groups")[0]["series"]["sum(quantity)"],
        }
    )
    events[TIME_COL] = pd.to_datetime(events[TIME_COL])
    events[ID_COL] = PROJECT_SLUG

    return events


def extract_error_data(events: pd.DataFrame) -> pd.DataFrame:
    error_events = events.query("`event.type` == 'error'")
    resampled_events = (
        error_events.groupby(ID_COL)
        .resample(FREQ, on=TIME_COL)
        .size()
        .reset_index()
        .rename(columns={0: TARGET_COL})
    )
    resampled_events = fill_gaps(
        resampled_events,
        freq=FREQ,
        time_col=TIME_COL,
        id_col=ID_COL,
        start="global",
        end=current_time,
    )
    resampled_events[TARGET_COL] = resampled_events[TARGET_COL].fillna(0)
    return resampled_events


def summarize(anomaly_online: pd.DataFrame) -> pd.DataFrame:
    # Summarize anomalies ----
    anomaly_summary = (
        anomaly_online.query("anomaly == True")
        .groupby(ID_COL)
        .agg({"anomaly": "sum", TIME_COL: "max", TARGET_COL: "last"})
        .reset_index()
        .rename(columns={TIME_COL: "last_time", TARGET_COL: "last_value"})
    )
    return anomaly_summary


def report_anomalies(anomaly_summary):
    # Report anomalies ----
    if anomaly_summary["anomaly"].sum() > 0:
        html_summary = anomaly_summary.to_html(index=False, border=0, justify="center")
        params: resend.Emails.SendParams = {
            "from": os.getenv("EMAIL_FROM"),
            "to": [os.getenv("EMAIL_TO")],
            "subject": f"Anomaly Detection Summary | {current_time}",
            "html": f"""
                "<html>
                    <body>
                        <h2>Anomaly Detection Summary</h2>
                        {html_summary}
                    </body>
                </html>
                """,
        }
        _ = resend.Emails.send(params)
        print("Email sent successfully!")
    else:
        print("No anomalies detected.")


# Step 1: Retrieve Sentry events ----
error_events = get_sentry_events_data()

# # Step 2: Extract error events ----
# error_events = extract_error_data(events=events)

# Step 3: Detect anomalies ----
anomaly_online = nixtla_client.detect_anomalies_online(
    error_events,
    id_col=ID_COL,
    time_col=TIME_COL,
    target_col=TARGET_COL,
    freq=FREQ,
    h=1,
    level=99,
    detection_size=24,  # last 1 hour
    threshold_method="univariate",  # Specify the threshold_method as 'univariate'
)

# Step 4: Summarize & Report anomalies ----
anomaly_summary = summarize(anomaly_online=anomaly_online)
report_anomalies(anomaly_summary=anomaly_summary)
