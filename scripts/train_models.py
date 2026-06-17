#!/usr/bin/env python3
import os
import pickle
import pandas as pd
from sklearn.ensemble import IsolationForest

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)

def preprocess_data(csv_path):
    print(f"[*] Loading dataset from {csv_path}...")
    df = pd.read_csv(csv_path)
    
    # Feature Engineering: Combine metric and interface into unified features
    # Example: 'cpu_usage' + 'none' -> 'cpu_usage_none', 'tx_bytes' + 'eth1' -> 'tx_bytes_eth1'
    df['feature_name'] = df['metric'] + "_" + df['interface']
    
    # Pivot the data so we have a tabular shape: Timestamp x Node as index, features as columns
    print("[*] Pivoting telemetry metrics into a feature matrix...")
    df_pivot = df.pivot_table(
        index=['timestamp', 'node'], 
        columns='feature_name', 
        values='value'
    ).reset_index()
    
    # Fill missing interfaces (e.g. branch nodes don't have eth2/eth3) with 0
    df_pivot.fillna(0, inplace=True)
    return df_pivot

def train_node_models(df_pivot):
    nodes = df_pivot['node'].unique()
    
    for node in nodes:
        print(f"\n[*] Training anomaly model for node: [{node}]...")
        # Filter rows belonging to this router
        node_df = df_pivot[df_pivot['node'] == node].copy()
        
        # Sort by timestamp to find baseline partition
        node_df.sort_values('timestamp', inplace=True)
        
        # Pull only feature columns (exclude index helpers)
        feature_cols = [c for c in node_df.columns if c not in ['timestamp', 'node']]
        X = node_df[feature_cols].values
        
        # We assume the first 150 rows (roughly 5 minutes of baseline collection) are healthy
        baseline_size = min(150, len(X))
        X_train = X[:baseline_size]
        
        print(f"    - Dataset size: {len(X)} rows. Training on first {baseline_size} baseline rows.")
        
        # Train an Isolation Forest. 
        # contamination='auto' balances sensitivity without oversaturating alerts
        clf = IsolationForest(n_estimators=100, contamination='auto', random_state=42)
        clf.fit(X_train)
        
        # Save model and feature column names (so inference can map features in the exact same order)
        model_payload = {
            "model": clf,
            "feature_cols": feature_cols
        }
        
        model_path = os.path.join(MODEL_DIR, f"{node}_iso_forest.pkl")
        with open(model_path, 'wb') as f:
            pickle.dump(model_payload, f)
        print(f"[+] Successfully saved model to {model_path}")

def main():
    telemetry_csv = "network_telemetry.csv"
    if not os.path.exists(telemetry_csv):
        print(f"[-] Error: {telemetry_csv} not found. Please run your telemetry script first.")
        return
        
    df_pivot = preprocess_data(telemetry_csv)
    train_node_models(df_pivot)
    print("\n[+] Model training complete for all network nodes.")

if __name__ == "__main__":
    main()