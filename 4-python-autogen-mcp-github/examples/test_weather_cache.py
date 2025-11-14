"""
Test script to demonstrate weather caching functionality.

This script makes multiple requests to the weather tool to show:
1. First request (cache miss) - fetches from API
2. Subsequent requests (cache hits) - returns cached data
3. Cache statistics showing hit rate improvement
"""

import json
import time

import requests

# Configuration
AGENT_SERVER_URL = "http://localhost:8080"
CITY = "London"
NUM_REQUESTS = 5


def send_chat_request(message: str) -> dict:
    """Send a chat request to the agent server."""
    try:
        response = requests.post(
            f"{AGENT_SERVER_URL}/chat", json={"message": message}, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def main():
    """Run the weather cache test."""
    print("=" * 60)
    print("Weather Cache Test")
    print("=" * 60)
    print(f"\nTesting weather requests for: {CITY}")
    print(f"Number of requests: {NUM_REQUESTS}\n")

    # Get initial cache stats
    print("Getting initial cache stats...")
    result = send_chat_request("get cache stats")
    print(f"Response: {result.get('response', 'No response')}\n")

    # Make multiple weather requests
    print(f"\nMaking {NUM_REQUESTS} weather requests for {CITY}...")
    print("-" * 60)

    timings = []
    for i in range(1, NUM_REQUESTS + 1):
        print(f"\nRequest #{i}:")
        start = time.time()
        result = send_chat_request(f"what's the weather in {CITY}?")
        elapsed = time.time() - start
        timings.append(elapsed)

        response = result.get("response", "No response")
        print(f"  Response: {response}")
        print(f"  Time: {elapsed:.3f}s")

        # Small delay between requests
        if i < NUM_REQUESTS:
            time.sleep(0.5)

    # Get final cache stats
    print("\n" + "-" * 60)
    print("\nGetting final cache stats...")
    result = send_chat_request("get cache stats")

    try:
        stats_text = result.get("response", "{}")
        # Extract JSON from response if it's wrapped in text
        if "{" in stats_text and "}" in stats_text:
            json_start = stats_text.index("{")
            json_end = stats_text.rindex("}") + 1
            stats = json.loads(stats_text[json_start:json_end])

            print("\nCache Statistics:")
            print(f"  Hits: {stats.get('hits', 0)}")
            print(f"  Misses: {stats.get('misses', 0)}")
            print(f"  Cache Size: {stats.get('size', 0)}")
            print(f"  Hit Rate: {stats.get('hit_rate_percent', 0)}%")
    except (json.JSONDecodeError, ValueError):
        print(f"Raw response: {result.get('response', 'No response')}")

    # Show timing analysis
    print("\n" + "=" * 60)
    print("Timing Analysis:")
    print(f"  First request (cache miss): {timings[0]:.3f}s")
    if len(timings) > 1:
        avg_cached = sum(timings[1:]) / len(timings[1:])
        print(f"  Average cached requests: {avg_cached:.3f}s")
        speedup = (timings[0] / avg_cached) if avg_cached > 0 else 0
        print(f"  Speedup from caching: {speedup:.2f}x")

    print("\n" + "=" * 60)
    print("\n✓ Test complete!")
    print("\nNote: Cache entries expire after the configured TTL")
    print("(default: 10 minutes, configurable via WEATHER_CACHE_TTL_MINUTES)")


if __name__ == "__main__":
    main()
