import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv("llm-labeling/.env")
token = os.getenv("OLLAMA_API_KEY")
url = "https://gpu.snet.tu-berlin.de/echelon/ollama"

headers = {"Authorization": f"Bearer {token}"} if token else {}

try:
    resp = requests.get(f"{url.rstrip('/')}/api/tags", headers=headers, timeout=5)
    if resp.status_code == 200:
        models = resp.json().get("models", [])
        print(f"Available models on {url}:")
        for m in models:
            print(f"- {m['name']}")
    else:
        print(f"Error: Server returned status code {resp.status_code}")
        print(resp.text)
except Exception as e:
    print(f"Error connecting to Ollama: {e}")
