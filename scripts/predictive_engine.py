#!/usr/bin/env python3
import os
import sys
import time
import json
import pickle
import requests
import numpy as np
import pandas as pd
import hmac
# pyrefly: ignore [missing-import]
import redis
import hashlib

PROM_URL = "http://localhost:9090/api/v1/query"
MODEL_DIR = "models"
ALERT_DIR = "alerts"
os.makedirs(ALERT_DIR, exist_ok=True)

try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    print("[+] Redis connection successful.")
except Exception as e:
    print(f"[-] Redis connection failed: {e}")
    sys.exit(1)

def get_hmac_key():
    key_path = ".gap_key"
    if not os.path.exists(key_path):
        print(f"[-] Integrity Error: Cryptographic HMAC key file '{key_path}' not found. Please train models first.")
        sys.exit(1)
    with open(key_path, 'rb') as f:
        return f.read()

# Scrape the last 60 seconds of telemetry from Prometheus to evaluate trends
QUERIES = {
    "cpu_usage": "rate(container_cpu_usage_seconds_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2'}[10s])[1m:2s]",
    "mem_usage": "container_memory_usage_bytes{container_label_clab_node_name=~'hub|transit|branch-1|branch-2'}[1m:2s]",
    "rx_bytes": "rate(container_network_receive_bytes_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2',interface=~'eth1|eth2|eth3'}[10s])[1m:2s]",
    "tx_bytes": "rate(container_network_transmit_bytes_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2',interface=~'eth1|eth2|eth3'}[10s])[1m:2s]"
}

# Standard thresholds for calculating Time-To-Impact
THRESHOLDS = {
    "mem_usage": 104857600, # 100 MB (Critical ceiling for lightweight container nodes)
    "tx_bytes": 62500       # 500 Kbps (Bottleneck threshold of our simulated transit links)
}

def load_models():
    models = {}
    if not os.path.exists(MODEL_DIR):
        print(f"[-] Models directory {MODEL_DIR} not found. Run train_models.py first.")
        sys.exit(1)
        
    secret_key = get_hmac_key()
    
    for file in os.listdir(MODEL_DIR):
        if file.endswith("_iso_forest.pkl"):
            node = file.replace("_iso_forest.pkl", "")
            filepath = os.path.join(MODEL_DIR, file)
            with open(filepath, 'rb') as f:
                wrapper = pickle.load(f)
                
            if not isinstance(wrapper, dict) or "signature" not in wrapper or "data" not in wrapper:
                print(f"[-] Security Error: Model file {file} is not signed or is corrupted. Aborting.")
                sys.exit(1)
                
            signature = wrapper["signature"]
            data = wrapper["data"]
            
            # Recalculate HMAC
            expected = hmac.new(secret_key, data, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                print(f"[-] Security Integrity Error: Model file {file} HMAC signature mismatch! The model may have been tampered with. Aborting.")
                sys.exit(1)
                
            models[node] = pickle.loads(data)
    return models

def query_prometheus_range(query):
    try:
        response = requests.get(PROM_URL, params={'query': query}, timeout=3)
        if response.status_code == 200:
            return response.json().get('data', {}).get('result', [])
    except Exception as e:
        print(f"[-] Telemetry collection failed: {e}")
    return []

def get_live_metrics():
    records = []
    for metric_name, query in QUERIES.items():
        results = query_prometheus_range(query)
        for r in results:
            metric_data = r.get('metric', {})
            node = metric_data.get('container_label_clab_node_name', 'unknown')
            interface = metric_data.get('interface', 'none')
            
            # Prometheus range query returns a list of [timestamp, value] pairs
            values = r.get('values', [])
            for pair in values:
                records.append({
                    "timestamp": int(pair[0]),
                    "node": node,
                    "interface": interface,
                    "metric": metric_name,
                    "value": float(pair[1])
                })
    return pd.DataFrame(records) if records else pd.DataFrame()

def calculate_forecast(timestamps, values, threshold_val):
    """Calculate slope using linear regression and project Time-to-Impact in seconds."""
    if len(values) < 5:
        return None
    
    # Fit line: y = mx + c
    x = np.array(timestamps) - timestamps[0]  # Normalize time start
    y = np.array(values)
    slope, intercept = np.polyfit(x, y, 1)
    
    current_val = values[-1]
    
    # If metric is increasing toward limit
    if slope > 0.001 and current_val < threshold_val:
        seconds_to_impact = (threshold_val - current_val) / slope
        return max(1, int(seconds_to_impact))
    return None

def process_node_inference(node, node_data, model_payload):
    clf = model_payload["model"]
    feature_cols = model_payload["feature_cols"]
    
    # Combine metrics into unified features
    node_data['feature_name'] = node_data['metric'] + "_" + node_data['interface']
    
    # Pivot
    pivoted = node_data.pivot_table(
        index='timestamp', 
        columns='feature_name', 
        values='value'
    ).reset_index()
    
    # Ensure all trained columns exist, filled with 0 if missing
    for col in feature_cols:
        if col not in pivoted.columns:
            pivoted[col] = 0.0
            
    # Sort columns exactly matching the trained model's feature order
    X = pivoted[feature_cols].values
    
    # Evaluate the most recent observation
    latest_row = X[-1].reshape(1, -1)
    prediction = clf.predict(latest_row)[0] # 1 = normal, -1 = anomaly
    raw_score = clf.score_samples(latest_row)[0] # lower means more anomalous (usually in [-0.8, -0.4])
    
    # Map the anomaly score to an operator-friendly 0-100 scale
    # Raw scores around -0.4 to -0.8 map linearly to 20-100 severity
    severity_score = 0
    if prediction == -1:
        severity_score = int(min(100, max(10, (abs(raw_score) - 0.35) * 200)))
        
    # Analyze rolling trends for Time-To-Impact forecasting
    time_to_impact = "Infinite (Stable)"
    
    # Case A: Check for memory leak on node
    mem_series = pivoted.get('mem_usage_none')
    if mem_series is not None:
        t_sec = calculate_forecast(pivoted['timestamp'].tolist(), mem_series.tolist(), THRESHOLDS["mem_usage"])
        if t_sec:
            time_to_impact = f"{int(t_sec // 60)}m {int(t_sec % 60)}s (Memory Exhaustion)"

    # Case B: Check for bandwidth saturation (tx_bytes_eth1/eth2/eth3)
    for col in pivoted.columns:
        if col.startswith("tx_bytes_"):
            tx_series = pivoted[col]
            t_sec = calculate_forecast(pivoted['timestamp'].tolist(), tx_series.tolist(), THRESHOLDS["tx_bytes"])
            if t_sec:
                time_to_impact = f"{int(t_sec // 60)}m {int(t_sec % 60)}s (Bandwidth Bottleneck on {col.replace('tx_bytes_', '')})"

    return prediction, severity_score, time_to_impact

def main():
    print("[*] Loading trained node models...")
    models = load_models()
    print(f"[+] Loaded models for nodes: {list(models.keys())}")
    print("[*] Starting real-time predictive loops (Polling every 1s)...")
    
    while True:
        try:
            df_live = get_live_metrics()
            if not df_live.empty:
                # Group and evaluate per node
                for node, model_payload in models.items():
                    node_data = df_live[df_live['node'] == node]
                    if len(node_data) > 0:
                        pred, severity, tti = process_node_inference(node, node_data, model_payload)
                        
                        if pred == -1:
                            alert = {
                                "timestamp": int(time.time()),
                                "node": node,
                                "status": "ANOMALOUS",
                                "severity_score": severity,
                                "time_to_impact": tti,
                                "contributing_signals": node_data[node_data['timestamp'] == node_data['timestamp'].max()][['metric', 'interface', 'value']].to_dict(orient='records')
                            }
                            
                            # Publish alert to Redis
                            redis_client.set("latest_alert", json.dumps(alert))
                            redis_client.publish("alerts", json.dumps(alert))
                                
                            print(f"[!] ALERT PUBLISHED: Node [{node}] has elevated risk! Severity: {severity}/100. Est. Impact in: {tti}")
            
            time.sleep(1)
        except KeyboardInterrupt:
            print("\n[+] Inference engine closed.")
            break

if __name__ == "__main__":
    main()