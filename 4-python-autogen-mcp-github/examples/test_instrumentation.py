#!/usr/bin/env python3
"""
Test script to verify New Relic instrumentation enhancements.

This script tests:
- Calculator tool with custom attributes
- Weather tool with cache metrics and rate limit tracking
- File read tool with file size tracking
- Error handling with notice_error()
"""

import time

import requests

BASE_URL = "http://localhost:8080/chat"


def send_request(message: str) -> dict:
    """Send a chat request to the agent."""
    response = requests.post(
        BASE_URL,
        json={"message": message},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return response.json()


def test_calculator():
    """Test calculator with custom attributes."""
    print("\n=== Testing Calculator (Custom Attributes) ===")
    messages = [
        "multiply 42 and 7",
        "add 100 and 200",
        "divide 144 by 12",
    ]

    for msg in messages:
        print(f"\n→ {msg}")
        result = send_request(msg)
        print(f"← {result.get('response', 'Error')}")
        time.sleep(1)


def test_weather_cache():
    """Test weather with cache metrics."""
    print("\n=== Testing Weather (Cache Metrics & Rate Limits) ===")

    # First request - cache miss
    print("\n→ What's the weather in Paris? (Cache Miss)")
    result = send_request("what's the weather in Paris")
    print(f"← {result.get('response', 'Error')}")
    time.sleep(1)

    # Second request - cache hit
    print("\n→ What's the weather in Paris? (Cache Hit)")
    result = send_request("what's the weather in Paris")
    print(f"← {result.get('response', 'Error')}")
    time.sleep(1)

    # Third request - cache hit
    print("\n→ What's the weather in Paris? (Cache Hit)")
    result = send_request("what's the weather in Paris")
    print(f"← {result.get('response', 'Error')}")


def test_file_operations():
    """Test file read with custom attributes."""
    print("\n=== Testing File Read (Custom Attributes) ===")

    print("\n→ Read sample.txt")
    result = send_request("read the file sample.txt")
    response = result.get("response", "Error")
    print(f"← {response[:200]}... (truncated)")
    time.sleep(1)

    # Test error case - file not found
    print("\n→ Read nonexistent.txt (Error Test)")
    result = send_request("read the file nonexistent.txt")
    print(f"← {result.get('response', 'Error')}")


def test_error_handling():
    """Test error handling with notice_error()."""
    print("\n=== Testing Error Handling (notice_error) ===")

    # Invalid city - API error
    print("\n→ Weather for invalid city")
    result = send_request("what's the weather in XYZ999InvalidCity")
    print(f"← {result.get('response', 'Error')}")
    time.sleep(1)

    # Division by zero
    print("\n→ Divide by zero")
    result = send_request("divide 100 by 0")
    print(f"← {result.get('response', 'Error')}")


def main():
    """Run all tests."""
    print("=" * 60)
    print("New Relic Instrumentation Test Suite")
    print("=" * 60)

    try:
        test_calculator()
        test_weather_cache()
        test_file_operations()
        test_error_handling()

        print("\n" + "=" * 60)
        print("✓ All tests completed!")
        print("=" * 60)
        print("\nCheck New Relic APM for:")
        print("  • Custom attributes: calculator.*, weather.*, file.*")
        print("  • Custom metrics: Custom/Cache/*, Custom/Weather/*, Custom/File/*")
        print("  • Error traces with notice_error() details")
        print("  • Transaction names: Calculator, GetWeather, ReadFile")

    except (requests.RequestException, KeyError) as e:
        print(f"\n✗ Test failed: {e}")


if __name__ == "__main__":
    main()
