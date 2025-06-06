import os

import pandas as pd
import plotly.graph_objects as go
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()


def load_metrics(file):
    df = pd.read_csv(file)
    df["ds"] = pd.to_datetime(df["ds"])
    return df


@app.get("/", response_class=HTMLResponse)
def dashboard():
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        cpu = load_metrics(os.path.join(BASE_DIR, "cpu_metrics.csv"))
        mem = load_metrics(os.path.join(BASE_DIR, "memory_metrics.csv"))
    except Exception as e:
        return f"<h1>Error loading metrics: {e}</h1>"

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=cpu["ds"],
            y=cpu["y"],
            name="CPU Usage",
            line=dict(color="blue"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=mem["ds"],
            y=mem["y"],
            name="Memory Usage",
            line=dict(color="green"),
        )
    )

    fig.update_layout(
        title="CPU & Memory Usage (Resampled)",
        xaxis_title="Time",
        yaxis_title="Percent",
        height=500,
    )

    html_plot = fig.to_html(full_html=False)
    return f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="60">
        <title>System Dashboard</title>
    </head>
    <body>
        <h1>System Monitoring Dashboard</h1>
        {html_plot}
    </body>
    </html>
    """


if __name__ == "__main__":
    uvicorn.run("dashboard:app", host="0.0.0.0", port=8050, reload=True)
