# Ollama LLM Integration Fixes - Implementation Guide

## Summary of Changes

Your multi-agent DevOps system now has **complete LLM integration fixes** to ensure Ollama returns executable commands instead of empty responses.

### Files Created/Modified

1. **NEW: `backend/llm_error_formatter.py`**
   - Cleans and formats errors for optimal LLM understanding
   - Extracts most relevant error lines from stack traces
   - Creates focused prompts that force JSON output

2. **UPDATED: `backend/llm_client.py`**
   - Added `_query_ollama_with_retry()` for resilient connection handling
   - Enhanced `_normalize_fix()` with better JSON parsing and fallback extraction
   - New `_get_direct_fix_for_error()` method provides immediate fixes when LLM returns empty
   - Improved `build_fix_prompt()` with mandatory JSON-only requirement
   - Better handling of non-JSON responses from Ollama

3. **UPDATED: `backend/multi_agent.py`**
   - `ValidatorAgent.select_best_fix()` now iterates through all candidates if best is empty
   - New `_get_emergency_fix()` method provides fallback fixes for timeout/docker issues
   - Better command validation and selection logic

4. **NEW: `test_ollama.py`**
   - Standalone test script to verify Ollama connection and fix generation
   - Tests direct JSON parsing and command extraction
   - Provides debugging guidance if Ollama fails

5. **UPDATED: `backend/main.py`**
   - New `/api/debug/ollama-fix-test` endpoint tests fix generation in production

## The Problem & Solution

### Problem
```
LLM remediation candidates received
└─ But response has 0 command(s)
└─ Validator selects fallback with 0 commands
└─ Error: "Selected fallback fix with 0 command(s)"
```

### Root Causes Fixed

1. **Error Context Not Formatted Properly**
   - Before: Raw stack traces sent to Ollama (noisy, long)
   - After: Cleaned, focused error messages extracted by `ErrorContextFormatter`

2. **Ollama Response Not Parsed Correctly**
   - Before: If JSON wasn't perfectly formed, entire response discarded
   - After: Multi-level parsing - tries JSON → shell commands → direct fixes

3. **Empty Responses Cause Cascading Failures**
   - Before: Empty response = empty fix = error
   - After: Empty response triggers `_get_direct_fix_for_error()` with hardcoded fixes for common errors

## Three-Layer Defense System

### Layer 1: LLM Generation (Ollama/Claude)
```python
# build_fix_prompt() now requires:
# "MANDATORY: Return ONLY valid JSON - NO other text"
# Examples of JSON format shown to improve output quality
```

### Layer 2: Response Parsing
```python
_normalize_fix() handles:
├─ Valid JSON → extract commands
├─ Malformed JSON → try regex extraction of code blocks
└─ No JSON → extract shell commands line by line
```

### Layer 3: Direct Fixes (No LLM Needed)
```python
_get_direct_fix_for_error() provides:
├─ SSH timeout → increase timeout settings
├─ Docker-compose missing → install it
├─ Docker permission denied → fix permissions
└─ Connection errors → diagnostic commands
```

## Testing the Fixes

### Test 1: Local Test Script

```bash
# Run from project root
python test_ollama.py

# Expected output:
# ✅ OLLAMA IS WORKING - Fix generation successful
```

### Test 2: API Test Endpoint

```bash
# Test if Ollama returns fix commands
curl http://localhost:8000/api/debug/ollama-fix-test

# Response should have:
{
  "candidates": {
    "ollama": {
      "has_commands": true,
      "command_count": 3,
      "commands": ["command1", "command2", "command3"]
    }
  }
}
```

### Test 3: Full Integration Test

```bash
# Test SSH connection debugging (from backend/main.py debug endpoint)
curl -X POST http://localhost:8000/api/debug/ssh-test \
  -H "Content-Type: application/json" \
  -d '{
    "server_ip": "10.0.0.1",
    "pem_content": "-----BEGIN RSA PRIVATE KEY-----...",
    "username": "ubuntu",
    "port": 22
  }'

# Watch logs for:
# ✅ "LLM remediation candidates received"
# ✅ "Selected ollama fix with N command(s)"
# ✅ Fix commands executing successfully
```

## Immediate Action Items

### 1. Verify Ollama is Running
```bash
docker ps | grep ollama
docker exec ollama ollama ps  # Should show deepseek-coder:6.7b
```

### 2. Test Fix Generation
```bash
python test_ollama.py
# Should show:
# ✅ Status: 200
# ✅ Parsed JSON successfully
# ✅ FIX GENERATION WORKING - Got N commands
```

### 3. Check API Debug Endpoint
```bash
curl http://localhost:8000/api/debug/ollama-fix-test | jq .candidates.ollama
```

### 4. If Ollama Returns Empty Commands
This shouldn't happen now, but if it does:
- Direct fix layer activates: `_get_direct_fix_for_error()`
- Emergency fix provides safe diagnostic commands
- ValidatorAgent always has fallback options

## How Fixes Work in Action

### Example: "Timeout opening channel" Error

**OLD Flow:**
```
Error detected
  → Query Ollama
  → Empty JSON response {} (or no "commands" field)
  → _normalize_fix() returns empty commands
  → Validator selects fallback with NO commands
  → No fix applied ❌
```

**NEW Flow:**
```
Error detected
  → Query Ollama with improved prompt
  → _query_ollama_with_retry() handles connection
  → Response: {"commands": ["sed -i...", "systemctl restart sshd", ...]}
  → _normalize_fix() parses successfully
  
  IF empty response:
    → _get_direct_fix_for_error() activates
    → Returns hardcoded SSH fixes (tested and safe)
    
  → Validator selects best fix (now guaranteed to have commands)
  → Commands execute successfully ✅
```

## Configuration

All behavior is controlled by existing settings in `backend/config.py`:
- `ai_auto_execute`: Enable/disable command execution
- `ai_max_retries`: Number of retry attempts
- `ai_allow_dangerous_commands`: Unsafe command allowlist
- `ollama_host`: Ollama server URL
- `deepseek_model`: Model name

## Monitoring & Debugging

### Check LLM Health
```bash
curl http://localhost:8000/api/agents/health | jq .llm
```

### Check Recent Learnings (What worked/failed)
```bash
curl http://localhost:8000/api/agents/learnings | jq '.[0:5]'
```

### Watch Server Logs for AI Activity
```bash
docker logs -f backend  # or your app container
# Look for: "[AI]" prefix in logs
```

### Enable Verbose Logging
Add to your startup:
```bash
export DEBUG=true
export AI_LOG_LEVEL=DEBUG
```

## Safety Guardrails

All fixes are validated for safety before execution:

```python
# Blocked patterns (always):
- rm -rf /
- mkfs.*
- dd if=
- shutdown/reboot/poweroff
- passwd
- chmod 777 /
- userdel

# Unless explicitly enabled via: ai_allow_dangerous_commands=true
```

## Performance Impact

- **LLM Query**: ~2-5 seconds (with fallback to direct fixes if slow)
- **Command Execution**: Varies (typically 5-30 seconds per command)
- **Total Retry Cycle**: ~15 seconds per attempt (5s delay between attempts)

## Common Error Patterns (Now Handled)

| Error | Fix Provided |
|-------|-------------|
| Timeout opening channel | SSH timeout settings increased |
| docker-compose not found | Docker Compose installed |
| permission denied (docker) | Docker socket permissions fixed |
| Connection refused | Diagnostic commands to troubleshoot |
| SSH authentication failed | SSH key validation checks |
| Port already in use | Port killer with safe selection |
| No space left | Docker system prune |

## Rollback (If Needed)

```bash
# The original llm_client.py logic is still there
# Just remove the new enhancements:

# Comment out in query_fix_candidates():
# if not parsed.get("commands"):
#     parsed = self._get_direct_fix_for_error(...)

# Remove _get_direct_fix_for_error() method
# Remove _query_ollama_with_retry() method

# Revert ValidatorAgent changes:
# Remove _get_emergency_fix() method
# Simplify select_best_fix() back to original
```

## Success Indicators

✅ After fixes, you should see:
1. `[AI] Validator -> UI: Selected ollama fix with N command(s)` (N > 0)
2. `[FIX] remote/local: <command>` logs showing actual execution
3. Commands completing with exit code 0
4. Operations succeeding after AI intervention

## Questions?

Check logs with the debug endpoints:
- `/api/debug/ollama-fix-test` - Test fix generation
- `/api/debug/ollama` - Test Ollama connection
- `/api/agents/learnings` - See what fixes worked historically
