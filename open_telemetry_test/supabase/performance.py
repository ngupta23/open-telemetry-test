# https://supabase.com/docs/guides/telemetry/metrics

import os
import re
import threading
import time
from collections import deque
from datetime import datetime
from queue import Queue

import numpy as np
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

prev_total = None
prev_idle = None


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


# --- PARSE TOTAL & IDLE ---
def extract_total_and_idle(text):
    total = 0.0
    idle = 0.0
    for line in text.splitlines():
        if line.startswith("node_cpu_seconds_total"):
            match = re.search(r'mode="(\w+)".*} ([\d\.e\+]+)', line)
            if match:
                mode, val = match.groups()
                val = float(val)
                total += val
                if mode in ("idle", "iowait"):
                    idle += val
    return total, idle


# --- COMPUTE INTERVAL USAGE ---
def compute_cpu_usage(current_total, current_idle):
    global prev_total, prev_idle
    if prev_total is None or prev_idle is None:
        prev_total, prev_idle = current_total, current_idle
        return None  # skip first reading

    # print(f"Previous Total: {prev_total}, Previous Idle: {prev_idle}")
    # print(f"Current Total: {current_total}, Current Idle: {current_idle}")
    delta_total = current_total - prev_total
    delta_idle = current_idle - prev_idle
    # print(f"Delta Total: {delta_total}, Delta Idle: {delta_idle}")

    prev_total, prev_idle = current_total, current_idle

    if delta_total <= 0:
        return None  # avoid divide by zero or invalid values

    return 100 * (1 - delta_idle / delta_total)


def extract_memory_usage(text):
    mem_total = mem_available = None
    for line in text.splitlines():
        if "node_memory_MemTotal_bytes" in line and "{" in line:
            mem_total = float(line.split()[-1])
        elif "node_memory_MemAvailable_bytes" in line and "{" in line:
            mem_available = float(line.split()[-1])
        if mem_total is not None and mem_available is not None:
            break
    if mem_total and mem_available:
        used = mem_total - mem_available
        return 100 * used / mem_total
    return None


# --- DETECTION ---
def detect_anomaly_zscore(timestamps, usage_vals, threshold=ANOMALY_THRESHOLD) -> bool:
    if len(usage_vals) < 10:
        return False
    mean = np.mean(usage_vals)
    std = np.std(usage_vals)
    latest = usage_vals[-1]
    z = (latest - mean) / std if std > 0 else 0
    return abs(z) > threshold


def detect_anomaly_nixtla(timestamps, usage_vals) -> bool:
    data = pd.DataFrame({"ds": timestamps, "y": usage_vals})
    # Resample to minute frequency if not already
    data["ds"] = pd.to_datetime(data["ds"])
    data = data.set_index("ds").resample("1min").mean().interpolate().reset_index()
    print(data.tail())

    nixtla_client = NixtlaClient(
        # defaults to os.environ.get("NIXTLA_API_KEY")
    )

    try:
        anomaly_online = nixtla_client.detect_anomalies_online(
            data,
            time_col="ds",
            target_col="y",
            freq="min",  # Specify the frequency of the data
            h=1,  # Specify the forecast horizon
            level=99,  # Set the confidence level for anomaly detection
            detection_size=1,  # Number of steps to analyze for anomalies
        )
        anomaly = anomaly_online.tail(1)["anomaly"][0]
        print(f"Anomaly detected: {anomaly}")
    except Exception as e:
        print(f"⚠️ Error detecting anomaly: {e}")
        anomaly = False

    return anomaly


def cpu_detect_anomaly_loop():
    while True:
        last_timestamp, last_cpu_usage = cpu_queue.get()
        cpu_timestamp_window.append(last_timestamp)
        cpu_usage_window.append(last_cpu_usage)
        if detect_anomaly_nixtla(cpu_timestamp_window, cpu_usage_window):
            print(
                f"[{last_timestamp}] 🚨 Anomaly detected! CPU = {last_cpu_usage:.2f}%"
            )
        else:
            print(f"[{last_timestamp}] CPU Usage OK = {last_cpu_usage:.2f}%")
        cpu_queue.task_done()


def mem_detect_loop():
    while True:
        last_timestamp, last_mem_usage = mem_queue.get()
        mem_timestamp_window.append(last_timestamp)
        mem_usage_window.append(last_mem_usage)
        if detect_anomaly_nixtla(mem_timestamp_window, mem_usage_window):
            print(f"[{last_timestamp}] 🚨 MEMORY Anomaly: {last_mem_usage:.2f}%")
        else:
            print(f"[{last_timestamp}] MEM Usage OK = {last_mem_usage:.2f}%")
        mem_queue.task_done()


# --- SCRAPER LOOP (TIMED) ---
def scrape_metrics_loop():
    next_run = time.time()
    while True:
        timestamp = datetime.utcnow().isoformat()

        text = fetch_metrics()
        if text:
            # Get CPU Usage ----
            total, idle = extract_total_and_idle(text)
            cpu_usage = compute_cpu_usage(total, idle)

            # get Memory Usage ----
            mem_usage = extract_memory_usage(text)

            # Add to queue ----
            if cpu_usage is not None:
                cpu_queue.put((timestamp, cpu_usage))
            if mem_usage is not None:
                mem_queue.put((timestamp, mem_usage))

        # print(f"Time: {timestamp}, CPU Usage: {usage}")
        # wait exactly until next interval
        next_run += INTERVAL
        sleep_time = max(0, next_run - time.time())
        time.sleep(sleep_time)


# --- MAIN ---
if __name__ == "__main__":
    print("⏳ Starting CPU & Memory monitor with anomaly detection...")
    threading.Thread(target=cpu_detect_anomaly_loop, daemon=True).start()
    threading.Thread(target=mem_detect_loop, daemon=True).start()
    scrape_metrics_loop()
