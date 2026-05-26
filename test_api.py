#!/usr/bin/env python3
# test_api.py - Test script for the FastAPI application
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def print_header(text):
    """Print formatted header"""
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def test_root_endpoint():
    """Test root endpoint"""
    print_header("Testing Root Endpoint")
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def test_health_check():
    """Test health check endpoint"""
    print_header("Testing Health Check Endpoint")
    try:
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def test_deploy():
    """Test deploy endpoint"""
    print_header("Testing Deploy Endpoint")
    try:
        deploy_data = {
            "repo_url": "https://github.com/SaiGorijala/task-tracker.git",
            "github_token": "",
            "server_ip": "13.60.21.79",
            "pem_content": "mock-pem-content",
            "dockerhub_user": "testuser",
            "dockerhub_pass": "testpass"
        }
        
        resp = requests.post(f"{BASE_URL}/api/deploy", json=deploy_data)
        print(f"Status: {resp.status_code}")
        result = resp.json()
        print(f"Response:\n{json.dumps(result, indent=2)}\n")
        
        if resp.status_code == 200:
            session_id = result.get('session_id')
            return session_id
        return None
    except Exception as e:
        print(f"ERROR: {e}\n")
        return None

def test_status(session_id):
    """Test status endpoint"""
    print_header(f"Testing Status Endpoint (Session: {session_id})")
    try:
        resp = requests.get(f"{BASE_URL}/api/status/{session_id}")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def test_credentials(session_id):
    """Test credentials endpoint"""
    print_header(f"Testing Credentials Endpoint (Session: {session_id})")
    try:
        resp = requests.get(f"{BASE_URL}/api/credentials/{session_id}")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def test_agent_activity(session_id):
    """Test agent activity endpoint"""
    print_header(f"Testing Agent Activity Endpoint (Session: {session_id})")
    try:
        resp = requests.get(f"{BASE_URL}/api/agent-activity/{session_id}")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def test_llm_conversations():
    """Test LLM conversations endpoint"""
    print_header("Testing LLM Conversations Endpoint")
    try:
        resp = requests.get(f"{BASE_URL}/api/llm-conversations")
        print(f"Status: {resp.status_code}")
        print(f"Response:\n{json.dumps(resp.json(), indent=2)}\n")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}\n")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("  DevOps AI Multi-Agent Platform - API Test Suite")
    print("="*60)
    
    results = {}
    
    # Test basic endpoints
    results['root'] = test_root_endpoint()
    results['health'] = test_health_check()
    
    # Test deployment
    session_id = test_deploy()
    if session_id:
        print(f"✓ Deploy successful! Session ID: {session_id}\n")
        
        # Give pipeline time to start
        time.sleep(2)
        
        # Test session-specific endpoints
        results['status'] = test_status(session_id)
        results['credentials'] = test_credentials(session_id)
        results['agent_activity'] = test_agent_activity(session_id)
    else:
        print("✗ Deploy failed!\n")
        results['deploy'] = False
    
    # Test LLM conversations
    results['llm_conversations'] = test_llm_conversations()
    
    # Print summary
    print_header("Test Summary")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status} - {test_name}")
    print()

if __name__ == "__main__":
    main()
