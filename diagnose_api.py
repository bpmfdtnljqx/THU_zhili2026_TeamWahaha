"""
diagnose_api.py
---------------
Standalone diagnostic: tests DeepSeek API connectivity independently of the reranker.

Run:  python diagnose_api.py

Tests:
  1. API key format check
  2. Network reachability (DNS + TCP)
  3. Direct API call with minimal prompt
  4. Test with "deepseek-chat" model
  5. Test with alternative base URLs
  6. Test with alternative models
"""

import os
import sys
import json
import time
import socket

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── Color helpers (ANSI) ──
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def ok(msg):
    print(f"  {GREEN}✅ {msg}{RESET}")

def fail(msg):
    print(f"  {RED}❌ {msg}{RESET}")

def warn(msg):
    print(f"  {YELLOW}⚠ {msg}{RESET}")

def info(msg):
    print(f"  {BLUE}ℹ {msg}{RESET}")

def divider(title):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")


def test_api_key():
    """Check API key format."""
    divider("1. API Key Check")

    if not API_KEY:
        fail("DEEPSEEK_API_KEY is NOT set in .env")
        return False

    # DeepSeek keys start with 'sk-'
    if API_KEY.startswith("sk-"):
        ok(f"Key format looks valid (starts with 'sk-')")
        info(f"Key ends with: ...{API_KEY[-8:]}")
        info(f"Key length: {len(API_KEY)} chars")
        return True
    else:
        warn(f"Key does NOT start with 'sk-'. Starts with: '{API_KEY[:8]}...'")
        info("This may still work — just unusual for DeepSeek")
        return True  # Not fatal


def test_network():
    """Test DNS resolution and TCP connectivity."""
    divider("2. Network Reachability")

    host = "api.deepseek.com"
    port = 443

    # DNS check
    try:
        ip = socket.gethostbyname(host)
        ok(f"DNS resolved {host} → {ip}")
    except socket.gaierror as e:
        fail(f"DNS resolution failed for {host}: {e}")
        return False

    # TCP check
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        ok(f"TCP connection to {host}:{port} succeeded")
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        fail(f"TCP connection to {host}:{port} failed: {e}")
        warn("Check firewall, proxy, or VPN settings")
        return False

    return True


def test_api_call(label, url, api_key, model, timeout=15):
    """Make a single API call and report detailed results."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Reply in JSON only."},
            {"role": "user", "content": 'Say "hello" in Chinese. Output: {"word": "..."}'},
        ],
        "temperature": 0.0,
        "max_tokens": 50,
    }

    info(f"URL: {url}")
    info(f"Model: {model}")
    info(f"Sending request (timeout={timeout}s)...")

    t0 = time.time()
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        elapsed = time.time() - t0

        status = response.status_code
        body = response.text
        content_type = response.headers.get("Content-Type", "unknown")

        print(f"  Status: {status}")
        print(f"  Content-Type: {content_type}")
        print(f"  Body length: {len(body)} chars")
        print(f"  Latency: {elapsed:.2f}s")
        print(f"  Response headers:")
        for key in ["x-ratelimit-remaining", "x-ratelimit-limit",
                     "retry-after", "x-request-id", "server"]:
            val = response.headers.get(key)
            if val:
                print(f"    {key}: {val}")

        if status == 200:
            if not body.strip():
                fail("EMPTY response body (200 OK but no content)")
                return False

            if "text/html" in content_type:
                fail(f"Got HTML instead of JSON — wrong endpoint URL!")
                print(f"  Body preview: {body[:300]}")
                return False

            try:
                data = response.json()
            except json.JSONDecodeError:
                fail(f"Body is not valid JSON: {body[:300]}")
                return False

            # Check for error in response
            if "error" in data:
                err = data["error"]
                fail(f"API returned error: {err.get('message', err)}")
                print(f"  Error type: {err.get('type', 'unknown')}")
                print(f"  Error code: {err.get('code', 'unknown')}")
                return False

            # Check for choices
            choices = data.get("choices", [])
            if not choices:
                fail(f"No 'choices' in response. Keys: {list(data.keys())}")
                print(f"  Full body: {json.dumps(data, ensure_ascii=False)[:500]}")
                return False

            content = choices[0].get("message", {}).get("content", "")
            if content:
                ok(f"SUCCESS! Content: {content}")
                return True
            else:
                finish = choices[0].get("finish_reason", "unknown")
                fail(f"Empty content (finish_reason={finish})")
                print(f"  Full body: {json.dumps(data, ensure_ascii=False)[:500]}")
                return False

        elif status == 401:
            fail("401 Unauthorized — API key is INVALID or EXPIRED")
            print(f"  Body: {body[:500]}")
            return False

        elif status == 403:
            fail("403 Forbidden — API key lacks permission or account suspended")
            print(f"  Body: {body[:500]}")
            return False

        elif status == 429:
            fail("429 Rate Limited — too many requests")
            retry_after = response.headers.get("Retry-After", "unknown")
            print(f"  Retry-After: {retry_after}s")
            print(f"  Body: {body[:500]}")
            return False

        elif status == 404:
            fail(f"404 Not Found — check the URL: {url}")
            print(f"  Body: {body[:500]}")
            return False

        else:
            fail(f"Unexpected status {status}")
            print(f"  Body: {body[:500]}")
            return False

    except requests.exceptions.Timeout:
        elapsed = time.time() - t0
        fail(f"Timeout after {elapsed:.1f}s (limit was {timeout}s)")
        return False

    except requests.exceptions.ConnectionError as e:
        fail(f"Connection error: {e}")
        return False

    except Exception as e:
        fail(f"Unexpected error: {type(e).__name__}: {e}")
        return False


def main():
    print(f"\n{BOLD}🔍 DeepSeek API Diagnostic Tool{RESET}")
    print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Python: {sys.version}")

    results = {}

    # ── 1. API key check ──
    results["api_key"] = test_api_key()

    # ── 2. Network check ──
    results["network"] = test_network()

    if not results["network"]:
        print(f"\n{YELLOW}⚠ Network check failed — skipping API tests.{RESET}")
        print(f"  Check: firewall, proxy settings, VPN")
        print(f"  Try:  curl -v https://api.deepseek.com/v1/models")
        return 1

    # ── 3. Test with current config ──
    divider("3. API Call — Current Config")
    url_v1 = f"{BASE_URL}/v1/chat/completions"
    results["current_config"] = test_api_call(
        "Current config", url_v1, API_KEY, MODEL
    )

    # ── 4. Test without /v1 (common misconfig) ──
    if not results["current_config"]:
        divider("4. API Call — Without /v1 prefix (common misconfig)")
        url_no_v1 = f"{BASE_URL}/chat/completions"
        test_api_call("Without /v1", url_no_v1, API_KEY, MODEL)

    # ── 5. Test with fallback model ──
    if not results["current_config"]:
        divider("5. API Call — Fallback model: deepseek-chat")
        test_api_call("deepseek-chat", url_v1, API_KEY, "deepseek-chat")

    # ── 6. List available models ──
    divider("6. List Available Models")
    try:
        resp = requests.get(
            f"{BASE_URL}/v1/models",
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=10,
        )
        if resp.status_code == 200:
            models = resp.json().get("data", [])
            ok(f"Found {len(models)} models")
            for m in models[:10]:
                print(f"    - {m.get('id', 'unknown')}")
            if len(models) > 10:
                print(f"    ... and {len(models) - 10} more")
        else:
            warn(f"Could not list models: HTTP {resp.status_code}")
            print(f"  Body: {resp.text[:300]}")
    except Exception as e:
        warn(f"Model listing failed: {e}")

    # ── Summary ──
    divider("Summary")
    all_ok = all(results.values())
    if all_ok:
        ok("All checks passed! API is working correctly.")
        print("\n  If the reranker still fails, check:")
        print("  - Prompt size (too many candidates)")
        print("  - API response format (run test_reranker_parse.py)")
        return 0
    else:
        failed_tests = [k for k, v in results.items() if not v]
        fail(f"Failed tests: {', '.join(failed_tests)}")

        print(f"\n{YELLOW}  Troubleshooting suggestions:{RESET}")
        if not results.get("api_key"):
            print("  → Set DEEPSEEK_API_KEY in .env file")
            print("  → Get a key from: https://platform.deepseek.com/api_keys")
        if not results.get("network"):
            print("  → Check internet connection")
            print("  → Check firewall/proxy: some networks block API access")
            print("  → Try: ping api.deepseek.com")
        if not results.get("current_config"):
            print("  → Verify API key at https://platform.deepseek.com/api_keys")
            print("  → Check if your account has credits")
            print("  → Try a different model (edit DEEPSEEK_MODEL in .env)")
            print("  → Check if DEEPSEEK_BASE_URL needs /v1 or not")
        return 1


if __name__ == "__main__":
    sys.exit(main())
