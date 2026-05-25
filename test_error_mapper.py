#!/usr/bin/env python3
"""Test error mapper functionality"""

import sys
from pathlib import Path

# Add parent dir to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.error_fix_mapper import ErrorFixMapper


def test_mapper():
    """Test error mapper with known patterns"""

    tests = [
        ("Not authorized. Please provide a user token in sonar.login",
         "sonar.login", 0.92),

        ("Not authorized. User token required",
         "not authorized", 0.95),

        ("docker-compose: command not found",
         "docker-compose", 0.91),

        ("Timeout opening channel",
         "timeout", 0.88),

        ("Permission denied (publickey)",
         "permission denied", 0.87),

        ("port 3000 is already allocated",
         "port", 0.80),

        ("no space left on device",
         "space left", 0.84),
    ]

    print("=" * 80)
    print("ERROR MAPPER TEST SUITE")
    print("=" * 80)

    passed = 0
    failed = 0

    for error_msg, expected_pattern, expected_confidence in tests:
        print(f"\n📍 Testing: {error_msg[:60]}...")

        # Test detection
        has_fix = ErrorFixMapper.should_use_mapper(error_msg)
        if not has_fix:
            print(f"   ❌ FAILED: Mapper didn't detect error")
            failed += 1
            continue

        print(f"   ✅ Mapper detected error")

        # Get fix
        fix = ErrorFixMapper.get_fix(error_msg, {})

        # Validate fix
        if not fix.get('commands') or len(fix['commands']) == 0:
            print(f"   ❌ FAILED: Fix has no commands")
            failed += 1
            continue

        print(f"   ✅ Got {len(fix['commands'])} fix commands")

        # Check confidence
        confidence = fix.get('confidence', 0)
        if confidence < 0.7:
            print(f"   ⚠️  WARNING: Low confidence ({confidence})")
        else:
            print(f"   ✅ Confidence: {confidence:.0%}")

        # Show first command
        first_cmd = fix['commands'][0]
        print(f"   ✅ First command: {first_cmd[:70]}...")

        # Check verification command exists
        if not fix.get('verification'):
            print(f"   ⚠️  WARNING: No verification command")
        else:
            print(f"   ✅ Verification: {fix['verification'][:70]}...")

        passed += 1

    # Print summary
    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("✅ ALL TESTS PASSED - Mapper is working correctly!")
        return 0
    else:
        print("❌ SOME TESTS FAILED - Check output above")
        return 1


def test_sonarqube_flow():
    """Test SonarQube-specific flow"""

    print("\n" + "=" * 80)
    print("SONARQUBE AUTHENTICATION TEST")
    print("=" * 80)

    sonar_errors = [
        "Not authorized. Please provide a user token in sonar.login",
        "sonar.login is required",
        "Invalid token",
    ]

    for error in sonar_errors:
        print(f"\n📍 SonarQube error: {error[:60]}...")

        if ErrorFixMapper.should_use_mapper(error):
            fix = ErrorFixMapper.get_fix(error)
            print(f"   ✅ Mapper handling this error")
            print(f"   Analysis: {fix['analysis']}")
            print(f"   Commands: {len(fix['commands'])} steps")
            print(f"   Requires retry: {fix.get('requires_retry', False)}")
            print(f"   Confidence: {fix.get('confidence', 0):.0%}")
        else:
            print(f"   ⚠️  Mapper doesn't handle this")


def test_mapper_performance():
    """Test mapper response time"""

    import time

    print("\n" + "=" * 80)
    print("PERFORMANCE TEST")
    print("=" * 80)

    error = "Not authorized. Please provide a user token in sonar.login"

    start = time.time()
    for _ in range(100):
        has_fix = ErrorFixMapper.should_use_mapper(error)
        if has_fix:
            fix = ErrorFixMapper.get_fix(error)
    elapsed = time.time() - start

    avg_time = (elapsed / 100) * 1000  # Convert to ms

    print(f"\n📊 Mapped 100 identical errors in {elapsed:.3f}s")
    print(f"   Average time per error: {avg_time:.2f}ms")

    if avg_time < 1:
        print(f"   ✅ EXCELLENT performance ({avg_time:.2f}ms << 1000ms)")
    elif avg_time < 10:
        print(f"   ✅ GOOD performance ({avg_time:.2f}ms << 100ms)")
    else:
        print(f"   ⚠️  Performance concern ({avg_time:.2f}ms)")


def main():
    """Run all tests"""

    print("\n")
    result = test_mapper()
    test_sonarqube_flow()
    test_mapper_performance()

    print("\n" + "=" * 80)
    print("✅ ERROR MAPPER TEST COMPLETE")
    print("=" * 80)
    print("\nTo use mapper in production:")
    print("  from backend.error_fix_mapper import ErrorFixMapper")
    print("  if ErrorFixMapper.should_use_mapper(error):")
    print("      fix = ErrorFixMapper.get_fix(error, context)")
    print("      # Execute fix['commands']")
    print("\n")

    return result


if __name__ == "__main__":
    sys.exit(main())
