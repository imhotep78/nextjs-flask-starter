import ipaddress
import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

app = Flask(__name__)

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

ALLOWED_MODELS = {"llama3", "llama3.1", "llama3.2", "mistral", "phi3", "gemma2"}

_PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Return True only for public http/https URLs (blocks SSRF targets)."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = parsed.hostname or ""
    if re.match(r"^(localhost|.*\.local)$", hostname, re.IGNORECASE):
        return False
    try:
        addr = ipaddress.ip_address(hostname)
        if any(addr in net for net in _PRIVATE_RANGES):
            return False
    except ValueError:
        pass  # hostname is a domain name, not an IP — allow it
    return True


@app.route("/api/python")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/api/bot/crawl", methods=["POST"])
def crawl():
    """Crawl a URL and return its text content."""
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    if not _is_safe_url(url):
        return jsonify({"error": "url must be a public http/https address"}), 400

    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "ClawBot/1.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)
    return jsonify({"url": url, "content": text})


@app.route("/api/bot/chat", methods=["POST"])
def chat():
    """Send a prompt to the local Ollama LLM (no cloud token fees)."""
    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "").strip()
    model = data.get("model", "llama3")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if model not in ALLOWED_MODELS:
        return jsonify({"error": f"model must be one of: {', '.join(sorted(ALLOWED_MODELS))}"}), 400

    try:
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": str(exc)}), 502

    result = resp.json()
    return jsonify({"model": model, "response": result.get("response", "")})