# src/utils.py
import requests, json, time
from pathlib import Path

OLLAMA_EMBED_URL = "http://localhost:11435/api/embeddings"
OLLAMA_GEN_URL = "http://localhost:11435/api/generate"

def get_embedding_ollama(text, model="nomic-embed-text", timeout=15):
    """
    Returns embedding list or raises requests exception.
    """
    payload = {"model": model, "prompt": text}
    r = requests.post(OLLAMA_EMBED_URL, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    # Ollama embeddings endpoint returns {"embedding": [...]}
    return data.get("embedding")

def generate_with_ollama_stream(prompt, model="mistral:latest", timeout=120):
    """
    Calls Ollama /api/generate with stream=True and returns concatenated 'response' fields.
    If Ollama returns non-stream JSON (rare), tries parsing that too.
    """
    payload = {"model": model, "prompt": prompt}
    # Use streaming since Ollama often streams line-delimited JSON
    r = requests.post(OLLAMA_GEN_URL, json=payload, stream=True, timeout=timeout)
    # If non-2xx: raise
    try:
        r.raise_for_status()
    except Exception:
        # Provide helpful output
        text = r.text if hasattr(r, "text") else "<no text>"
        raise RuntimeError(f"Ollama generation failed: status={r.status_code}, text={text}")

    final = ""
    try:
        # iterate lines
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                j = json.loads(line)
            except Exception:
                # Sometimes the stream contains non-json (skip)
                continue
            # common key = "response"
            if "response" in j and j["response"] is not None:
                final += j["response"]
            # Some Ollama variants include "output" or "result"
            elif "output" in j and j["output"]:
                if isinstance(j["output"], str):
                    final += j["output"]
                elif isinstance(j["output"], dict) and "response" in j["output"]:
                    final += j["output"]["response"]
    except Exception as e:
        # If streaming fails, try to parse non-stream text
        try:
            blob = r.text
            jl = json.loads(blob)
            # try common keys
            final = jl.get("response") or jl.get("result") or jl.get("output") or ""
        except Exception:
            raise RuntimeError(f"Failed to read stream from Ollama: {e}")
    return final

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
