#!/usr/bin/env python3
import os
import json
import requests
# pyrefly: ignore [missing-import]
import chromadb
from populate_kb import OllamaEmbeddingFunction

CHROMA_PATH = "chroma_db"
ALERT_FILE = "alerts/latest_alert.json"
OLLAMA_GENERATE_URL = "http://localhost:11434/api/generate"

def load_latest_alert():
    if not os.path.exists(ALERT_FILE):
        return None
    try:
        with open(ALERT_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"[-] Error loading alert file: {e}")
        return None

def query_vector_db(query_text):
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = OllamaEmbeddingFunction()
    
    collection = client.get_collection(
        name="noc_playbooks",
        embedding_function=embedding_fn
    )
    
    # Retrieve the top 2 most matching documents based on local vector similarity
    results = collection.query(
        query_texts=[query_text],
        n_results=2
    )
    return results.get('documents', [[]])[0]

def query_copilot(prompt):
    payload = {
        "model": "llama3.2:3b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2, # Low temperature ensures highly deterministic, technical output
            "num_predict": 300  # Cap response length to keep CPU/GPU cycle memory bounded
        }
    }
    try:
        response = requests.post(OLLAMA_GENERATE_URL, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json().get('response', '')
    except Exception as e:
        return f"Local LLM Generation failed: {e}"
    return "No response from local Copilot."

def main():
    print("[*] Scanning for active predictive alerts...")
    alert = load_latest_alert()
    
    if not alert:
        print("[+] No active anomalies detected. System operating within healthy parameters.")
        return
        
    print(f"\n[!] ACTIVE ALERT DETECTED on Node [{alert['node']}]!")
    print(f"    - Severity: {alert['severity_score']}/100")
    print(f"    - Estimated Impact: {alert['time_to_impact']}")
    
    # Construct search query for ChromaDB
    search_query = f"Node {alert['node']} anomaly indicating {alert['time_to_impact']}"
    
    print("[*] Retrieving relevant topology map and SOP runbooks from local ChromaDB...")
    kb_docs = query_vector_db(search_query)
    context_text = "\n\n---\n\n".join(kb_docs)
    
    # Build System Prompt with retrieved facts
    prompt = f"""
    You are an expert offline, air-gapped AI Network Operations Center (NOC) Copilot.
    Analyze the following predictive network alert and provide a clean, technical response.

    [Predictive Alert Payload]
    - Detected Node: {alert['node']}
    - Alert Status: {alert['status']}
    - Risk Severity: {alert['severity_score']}/100
    - Time-to-Impact: {alert['time_to_impact']}
    - Top Contributing Signals: {json.dumps(alert['contributing_signals'])}

    [Retrieved Runbook & Topology Context]
    {context_text}

    [Output Requirements]
    Format your response in plain text with the following sections:
    1. DIAGNOSTIC HYPOTHESIS: Explain why this alert occurred.
    2. ESTIMATED RISK SCOPE: Which node and paths are threatened and when.
    3. MITIGATION ACTIONS: Provide the exact commands/actions the operator must run to resolve this issue. Keep steps short and accurate.
    """
    
    print("[*] Generating offline mitigation recommendation via local Llama-3.2...")
    recommendation = query_copilot(prompt)
    
    print("\n================== COPILOT OPERATOR RECOMMENDATION ==================")
    print(recommendation)
    print("=====================================================================")

if __name__ == "__main__":
    main()