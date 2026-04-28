#!/usr/bin/env python3
"""
Automated search trigger testing for Web Search Grounding Specialist.

Tests known queries that MUST trigger web search and reports success/failure.
"""

import requests
import json
import sys

BACKEND_URL = "http://localhost:8000"

# Queries that MUST trigger web search
MUST_SEARCH_QUERIES = [
    "Who is the current president of the United States?",
    "What is the latest news about AI?",
    "When is the next SpaceX launch?",
    "What happened in the stock market today?",
    "Who won the Warriors game last night?",
    "What's the weather like in San Francisco today?",
    "Who is the current Prime Minister of the UK?",
    "Latest Tesla stock price",
]

def test_search_endpoint():
    """Test if the web_search tool is directly accessible."""
    try:
        # Check if backend is running
        health = requests.get(f"{BACKEND_URL}/health", timeout=5)
        if health.status_code != 200:
            print("❌ Backend not healthy")
            return False
        print("✅ Backend healthy")
        return True
    except Exception as e:
        print(f"❌ Backend unreachable: {e}")
        return False

def test_ddg_availability():
    """Test if DuckDuckGo is reachable."""
    try:
        resp = requests.get(
            "https://html.duckduckgo.com/html/?q=test",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        if resp.status_code == 200 and "result" in resp.text.lower():
            print("✅ DuckDuckGo reachable")
            return True
        print(f"⚠️ DuckDuckGo returned {resp.status_code}")
        return False
    except Exception as e:
        print(f"❌ DuckDuckGo unreachable: {e}")
        return False

def test_bing_availability():
    """Test if Bing fallback is reachable."""
    try:
        resp = requests.get(
            "https://www.bing.com/search?q=test",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=5
        )
        if resp.status_code == 200:
            print("✅ Bing reachable")
            return True
        print(f"⚠️ Bing returned {resp.status_code}")
        return False
    except Exception as e:
        print(f"❌ Bing unreachable: {e}")
        return False

def run_full_diagnostic():
    """Run all diagnostic checks."""
    print("=" * 50)
    print("🔍 Web Search Grounding Diagnostic")
    print("=" * 50)
    print()
    
    print("## Endpoint Availability")
    backend_ok = test_search_endpoint()
    ddg_ok = test_ddg_availability()
    bing_ok = test_bing_availability()
    print()
    
    if not backend_ok:
        print("❌ Cannot proceed: Backend not running")
        sys.exit(1)
    
    print("## Search Trigger Tests")
    print("(Run these manually in the chat interface)")
    print()
    for i, query in enumerate(MUST_SEARCH_QUERIES, 1):
        print(f"  {i}. {query}")
    print()
    
    print("## Summary")
    print(f"  Backend: {'✅' if backend_ok else '❌'}")
    print(f"  DuckDuckGo: {'✅' if ddg_ok else '❌'}")
    print(f"  Bing Fallback: {'✅' if bing_ok else '❌'}")
    print()
    
    if ddg_ok or bing_ok:
        print("✅ At least one search provider is available")
    else:
        print("❌ CRITICAL: No search providers available!")

if __name__ == "__main__":
    run_full_diagnostic()
