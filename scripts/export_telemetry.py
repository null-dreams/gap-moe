#!/usr/bin/env python3
import os
import time
import requests
import pandas as pd

PROM_URL = "http://localhost:9090/api/v1/query"
OUTPUT_FILE = "network_telemetry.csv"

# Prometheus PromQL Queries mapped to features
QUERIES = {
    "cpu_usage": "rate(container_cpu_usage_seconds_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2'}[10s])",
    "mem_usage": "container_memory_usage_bytes{container_label_clab_node_name=~'hub|transit|branch-1|branch-2'}",
    "rx_bytes": "rate(container_network_receive_bytes_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2',interface=~'eth1|eth2|eth3'}[10s])",
    "tx_bytes": "rate(container_network_transmit_bytes_total{container_label_clab_node_name=~'hub|transit|branch-1|branch-2',interface=~'eth1|eth2|eth3'}[10s])"
}

def query_prometheus(query):
    try:
        response = requests.get(PROM_URL, params={'query': query}, timeout=5)
        if response.status_code == 200:
            return response.json().get('data', {}).get('result', [])
    except Exception as e:
        print(f"[-] Error querying Prometheus: {e}")
    return []

def scrape_data():
    current_time = time.time()
    records = []
    
    for metric_name, query in QUERIES.items():
        results = query_prometheus(query)
        for r in results:
            metric_data = r.get('metric', {})
            node = metric_data.get('container_label_clab_node_name', 'unknown')
            interface = metric_data.get('interface', 'none')
            
            # Extract value
            value_pair = r.get('value', [])
            if len(value_pair) == 2:
                val = float(value_pair[1])
                
                records.append({
                    "timestamp": int(current_time),
                    "node": node,
                    "interface": interface,
                    "metric": metric_name,
                    "value": val
                })
                
    return records

def main():
    print(f"[*] Telemetry exporter running. Saving data to '{OUTPUT_FILE}'...")
    print("[*] Press Ctrl+C to terminate.")
    
    while True:
        try:
            new_records = scrape_data()
            if new_records:
                df_new = pd.DataFrame(new_records)
                
                # Append to CSV
                if not os.path.exists(OUTPUT_FILE):
                    df_new.to_csv(OUTPUT_FILE, index=False)
                else:
                    df_new.to_csv(OUTPUT_FILE, mode='a', header=False, index=False)
                    
            time.sleep(2) # Scrape matches Prometheus interval
        except KeyboardInterrupt:
            print("\n[+] Exporting terminated gracefully.")
            break

if __name__ == "__main__":
    main()