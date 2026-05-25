#!/usr/bin/env python3
"""Test Ollama connection and fix generation"""

import json
import requests
import sys
from pathlib import Path


def test_ollama(host: str = "http://localhost:11434", model: str = "deepseek-coder:6.7b"):
    """Test if Ollama returns valid commands"""

    print("=" * 80)
    print("OLLAMA FIX GENERATION TEST")
    print("=" * 80)

    # Test 1: Basic connectivity
    print("\n1. Testing connectivity to Ollama...")
    try:
        resp = requests.get(f"{host}/api/tags", timeout=5)
        print(f"   ✅ Status: {resp.status_code}")
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            print(f"   Available models: {model_names}")
            if model not in str(model_names):
                print(f"   ⚠️  Model {model} not found locally")
        else:
            print(f"   ❌ Unexpected status")
            return False
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return False

    # Test 2: Generate fix for SSH timeout
    print("\n2. Testing fix generation for SSH timeout...")
    prompt = """You are a DevOps remediation agent.

ERROR: Timeout opening channel
Exit Code: 1

REQUIREMENTS
1. Return exact bash commands that are safe and idempotent.
2. Include a verification command when possible.

MANDATORY: Return ONLY valid JSON - NO other text:
{
  "analysis": "brief explanation",
  "commands": ["command1", "command2"],
  "verification": "command that proves it worked",
  "confidence": 0.75
}"""

    try:
        response = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()
            raw_response = result.get("response", "")
            print(f"   Raw response length: {len(raw_response)}")
            print(f"   Raw response (first 200 chars): {raw_response[:200]}")

            # Try to parse JSON
            try:
                # Try direct parse
                data = json.loads(raw_response.strip())
                print(f"   ✅ Parsed JSON successfully")
                print(f"   Commands: {len(data.get('commands', []))} found")
                print(f"   Analysis: {data.get('analysis', '')[:100]}")

                if data.get("commands"):
                    print(f"   ✅ FIX GENERATION WORKING - Got {len(data['commands'])} commands")
                    for i, cmd in enumerate(data['commands'], 1):
                        print(f"      {i}. {cmd[:80]}")
                    return True
                else:
                    print(f"   ⚠️  JSON parsed but no commands in response")

            except json.JSONDecodeError as e:
                print(f"   ❌ Could not parse response as JSON: {e}")
                print(f"   Response preview: {raw_response[:500]}")

        else:
            print(f"   ❌ Failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")

    except requests.Timeout:
        print(f"   ❌ Request timeout (>60s)")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: Direct command generation (simpler test)
    print("\n3. Testing direct command generation...")
    try:
        response = requests.post(
            f"{host}/api/generate",
            json={
                "model": model,
                "prompt": 'Return only JSON: {"commands": ["echo test"]}',
                "stream": False,
                "max_tokens": 100,
            },
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            print(f"   Response: {result.get('response', '')[:150]}")
            return True
    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    return False


def main():
    host = "http://localhost:11434"
    model = "deepseek-coder:6.7b"

    if len(sys.argv) > 1:
        host = sys.argv[1]
    if len(sys.argv) > 2:
        model = sys.argv[2]

    print(f"\nTesting Ollama at: {host}")
    print(f"Model: {model}\n")

    success = test_ollama(host, model)

    print("\n" + "=" * 80)
    if success:
        print("✅ OLLAMA IS WORKING - Fix generation successful")
        sys.exit(0)
    else:
        print("❌ OLLAMA FIX GENERATION ISSUE - See details above")
        print("\nDEBUGGING STEPS:")
        print("1. Check if Ollama container is running: docker ps | grep ollama")
        print("2. Check Ollama logs: docker logs ollama")
        print("3. Pull the model manually: docker exec ollama ollama pull deepseek-coder:6.7b")
        print("4. Verify model is loaded: docker exec ollama ollama ps")
        sys.exit(1)


if __name__ == "__main__":
    main()
