#!/bin/bash
# Verify all LLM integration fixes are in place

echo "🔍 Verifying Ollama LLM Integration Fixes..."
echo "================================================"

ERRORS=0

# Check 1: Error formatter exists
if [ -f "backend/llm_error_formatter.py" ]; then
    echo "✅ backend/llm_error_formatter.py exists"
    if grep -q "def format_for_ollama" backend/llm_error_formatter.py; then
        echo "   ✅ format_for_ollama method found"
    else
        echo "   ❌ format_for_ollama method NOT found"
        ((ERRORS++))
    fi
else
    echo "❌ backend/llm_error_formatter.py NOT found"
    ((ERRORS++))
fi

# Check 2: LLM client updated
if grep -q "_query_ollama_with_retry" backend/llm_client.py; then
    echo "✅ backend/llm_client.py has _query_ollama_with_retry method"
else
    echo "❌ backend/llm_client.py missing _query_ollama_with_retry"
    ((ERRORS++))
fi

if grep -q "_get_direct_fix_for_error" backend/llm_client.py; then
    echo "✅ backend/llm_client.py has _get_direct_fix_for_error method"
else
    echo "❌ backend/llm_client.py missing _get_direct_fix_for_error"
    ((ERRORS++))
fi

# Check 3: Multi-agent updated
if grep -q "_get_emergency_fix" backend/multi_agent.py; then
    echo "✅ backend/multi_agent.py has _get_emergency_fix method"
else
    echo "❌ backend/multi_agent.py missing _get_emergency_fix"
    ((ERRORS++))
fi

# Check 4: Test script exists
if [ -f "test_ollama.py" ]; then
    echo "✅ test_ollama.py test script exists"
else
    echo "❌ test_ollama.py NOT found"
    ((ERRORS++))
fi

# Check 5: Debug endpoint in main.py
if grep -q "debug_ollama_fix_test" backend/main.py; then
    echo "✅ backend/main.py has /api/debug/ollama-fix-test endpoint"
else
    echo "❌ backend/main.py missing debug endpoint"
    ((ERRORS++))
fi

# Check 6: Documentation exists
if [ -f "FIXES_APPLIED.md" ]; then
    echo "✅ FIXES_APPLIED.md documentation created"
else
    echo "❌ FIXES_APPLIED.md NOT found"
    ((ERRORS++))
fi

echo "================================================"
if [ $ERRORS -eq 0 ]; then
    echo "✅ ALL CHECKS PASSED - Ready to test!"
    echo ""
    echo "Next steps:"
    echo "1. Run: python test_ollama.py"
    echo "2. Check: curl http://localhost:8000/api/debug/ollama-fix-test"
    echo "3. Monitor logs for '[AI]' prefix entries"
else
    echo "❌ Found $ERRORS issues - check output above"
fi
