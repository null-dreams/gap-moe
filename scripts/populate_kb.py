#!/usr/bin/env python3
import os
import requests
# pyrefly: ignore [missing-import]
import chromadb
# pyrefly: ignore [missing-import]
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

CHROMA_PATH = "chroma_db"
KB_DIR = "knowledge"

# Custom ChromaDB Embedding class to utilize Ollama's local nomic-embed-text API (100% Air-gapped)
class OllamaEmbeddingFunction(EmbeddingFunction):
    def __init__(self, url="http://localhost:11434/api/embeddings", model_name="nomic-embed-text"):
        self.url = url
        self.model_name = model_name

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                response = requests.post(
                    self.url,
                    json={"model": self.model_name, "prompt": text},
                    timeout=30
                )
                if response.status_code == 200:
                    embeddings.append(response.json()["embedding"])
                else:
                    raise Exception(f"Ollama returned status code {response.status_code}")
            except Exception as e:
                print(f"[-] Failed to generate local embedding: {e}")
                # Fallback to zero-vector to prevent crash during offline demo
                embeddings.append([0.0] * 768) 
        return embeddings

def main():
    print("[*] Initializing local persistent ChromaDB client...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    
    # Initialize the database collection with our custom air-gapped embedding function
    embedding_fn = OllamaEmbeddingFunction()
    collection = client.get_or_create_collection(
        name="noc_playbooks",
        embedding_function=embedding_fn
    )
    
    if not os.path.exists(KB_DIR):
        print(f"[-] Knowledge base directory '{KB_DIR}' not found.")
        return

    print("[*] Reading local markdown playbooks...")
    documents = []
    metadatas = []
    ids = []
    
    for idx, filename in enumerate(os.listdir(KB_DIR)):
        if filename.endswith(".md"):
            filepath = os.path.join(KB_DIR, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            documents.append(content)
            metadatas.append({"source": filename})
            ids.append(f"doc_{idx}")
            print(f"  - Parsed {filename}")
            
    if documents:
        print("[*] Generating local vector embeddings and indexing runbooks...")
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"[+] Successfully indexed {len(documents)} documents inside ChromaDB at '{CHROMA_PATH}'.")
    else:
        print("[-] No markdown playbooks found to index.")

if __name__ == "__main__":
    main()