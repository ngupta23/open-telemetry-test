# https://supabase.com/docs/guides/telemetry/metrics

import glob
import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from queue import Queue

import pandas as pd
import requests  # type: ignore
from dotenv import load_dotenv
from nixtla import NixtlaClient
from requests.auth import HTTPBasicAuth  # type: ignore

load_dotenv()

# --- CONFIGURATION ---
SUPABASE_PROJECT = os.getenv("SUPABASE_PROJECT")
SUPABASE_JWT = os.getenv("SUPABASE_JWT")
if not SUPABASE_PROJECT or not SUPABASE_JWT:
    raise ValueError(
        "Please set SUPABASE_PROJECT and SUPABASE_JWT environment variables."
    )

# Supabase only collects it's metrics every 60 seconds
# (sends to Prometheus at this frequency)
INTERVAL = 60  # seconds
MAX_WINDOW_SIZE = 180
ANOMALY_THRESHOLD = 3.0

# --- SHARED STATE ---
# Queue for shared data across threads
cpu_queue: Queue = Queue()
mem_queue: Queue = Queue()

# Sliding window of length MAX_WINDOW_SIZE
cpu_timestamp_window: deque = deque(maxlen=MAX_WINDOW_SIZE)
cpu_usage_window: deque = deque(maxlen=MAX_WINDOW_SIZE)
mem_timestamp_window: deque = deque(maxlen=MAX_WINDOW_SIZE)
mem_usage_window: deque = deque(maxlen=MAX_WINDOW_SIZE)


# cpu_data = []
# mem_data = []
# data_lock = threading.Lock()


# --- CPU State ---
class CPUTracker:
    def __init__(self):
        self.prev_total = None
        self.prev_idle = None

    def compute_usage(self, total, idle):
        if self.prev_total is None:
            self.prev_total, self.prev_idle = total, idle
            return None
        delta_total = total - self.prev_total
        delta_idle = idle - self.prev_idle
        self.prev_total, self.prev_idle = total, idle
        return 100 * (1 - delta_idle / delta_total) if delta_total > 0 else None


# --- METRICS ---
def fetch_metrics():
    url = f"https://{SUPABASE_PROJECT}.supabase.co/customer/v1/privileged/metrics"
    auth = HTTPBasicAuth("service_role", SUPABASE_JWT)
    try:
        response = requests.get(url, auth=auth, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] ⚠️ Error fetching metrics: {e}")
        return None


def parse_prometheus_metrics(text):
    metrics: dict = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        try:
            key = line.split()[0].split("{")[0]
            value = float(line.split()[-1])
            metrics.setdefault(key, []).append((line, value))
        except Exception:
            continue
    return metrics


# --- PARSE TOTAL & IDLE ---
def extract_total_and_idle(metrics):
    total, idle = 0.0, 0.0
    for line, val in metrics.get("node_cpu_seconds_total", []):
        match = re.search(r'mode="(\w+)"', line)
        if match:
            mode = match.group(1)
            total += val
            if mode in ("idle", "iowait"):
                idle += val
    return total, idle


def extract_memory_usage(metrics):
    mem_total = mem_available = None
    for _, val in metrics.get("node_memory_MemTotal_bytes", []):
        mem_total = val
    for _, val in metrics.get("node_memory_MemAvailable_bytes", []):
        mem_available = val
    return (
        100 * (mem_total - mem_available) / mem_total
        if mem_total and mem_available
        else None
    )


# --- DETECTION ---
def detect_anomaly_nixtla(timestamps, usage_vals, export_path=None):
    df = pd.DataFrame({"ds": timestamps, "y": usage_vals})
    df["ds"] = pd.to_datetime(df["ds"])
    df = df.set_index("ds").resample("1min").mean().interpolate().reset_index()

    if export_path:
        df.to_csv(export_path, index=False)
        print(f"📁 Exported: {export_path}")

    if len(df) < 10:
        return False

    try:
        client = NixtlaClient()
        result = client.detect_anomalies_online(
            df,
            time_col="ds",
            target_col="y",
            freq="min",
            h=1,
            level=99,
            detection_size=1,
        )
        return result.tail(1)["anomaly"].iloc[0]
    except Exception as e:
        print(f"⚠️ Nixtla error: {e}")
        return False


def detect_loop(name, queue, ts_window, usage_window, export_path):
    while True:
        ts, usage = queue.get()
        ts_window.append(ts)
        usage_window.append(usage)

        # with data_lock:
        #     store.append({"timestamp": ts, "value": usage})

        if detect_anomaly_nixtla(ts_window, usage_window, export_path):
            print(f"[{ts}] 🚨 {name} Anomaly: {usage:.2f}%")
        else:
            print(f"[{ts}] {name} OK: {usage:.2f}%")

        queue.task_done()


# --- SCRAPE LOOP ---
def scrape_loop():
    tracker = CPUTracker()
    next_run = time.monotonic()
    while True:
        ts = datetime.utcnow().isoformat()
        text = fetch_metrics()
        if text:
            metrics = parse_prometheus_metrics(text)
            total, idle = extract_total_and_idle(metrics)
            cpu_usage = tracker.compute_usage(total, idle)
            mem_usage = extract_memory_usage(metrics)
            if cpu_usage is not None:
                cpu_queue.put((ts, cpu_usage))
            if mem_usage is not None:
                mem_queue.put((ts, mem_usage))
        next_run += INTERVAL
        time.sleep(max(0, next_run - time.monotonic()))


# --- MAIN ---
if __name__ == "__main__":
    print("⏳ Monitoring started...")

    # Delete existing metrics files
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    for f in glob.glob(os.path.join(BASE_DIR, "*_metrics.csv")):
        try:
            os.remove(f)
            print(f"🗑️ Deleted: {f}")
        except Exception as e:
            print(f"⚠️ Could not delete {f}: {e}")

    threading.Thread(
        target=detect_loop,
        args=(
            "CPU",
            cpu_queue,
            cpu_timestamp_window,
            cpu_usage_window,
            # cpu_data,
            os.path.join(BASE_DIR, "cpu_metrics.csv"),
        ),
        daemon=True,
    ).start()
    threading.Thread(
        target=detect_loop,
        args=(
            "MEM",
            mem_queue,
            mem_timestamp_window,
            mem_usage_window,
            os.path.join(BASE_DIR, "memory_metrics.csv"),
        ),
        daemon=True,
    ).start()
    try:
        scrape_loop()
    except KeyboardInterrupt:
        print("🛑 Exiting...")
