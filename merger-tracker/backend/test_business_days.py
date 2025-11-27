#!/usr/bin/env python3
"""Test business day calculations according to ACCC Act."""

from business_days import calculate_business_days, is_business_day
from datetime import datetime

def test_business_days():
    """Test various business day scenarios."""

    print("Testing Business Day Calculations")
    print("=" * 50)

    # Test 1: Simple weekday range (Mon-Fri)
    # 2025-03-03 (Mon) to 2025-03-07 (Fri) = 5 business days
    result = calculate_business_days("2025-03-03T00:00:00Z", "2025-03-07T00:00:00Z")
    print(f"\nTest 1: Mon-Fri (5 business days)")
    print(f"2025-03-03 to 2025-03-07: {result} business days")
    assert result == 5, f"Expected 5, got {result}"
    print("✓ PASSED")

    # Test 2: Range including a weekend and Canberra Day
    # 2025-03-03 (Mon) to 2025-03-10 (Mon) = 5 business days
    # (Mon-Fri = 5 days, Sat/Sun excluded, Mon is Canberra Day so excluded)
    result = calculate_business_days("2025-03-03T00:00:00Z", "2025-03-10T00:00:00Z")
    print(f"\nTest 2: Mon-Mon including weekend and Canberra Day")
    print(f"2025-03-03 to 2025-03-10: {result} business days")
    print(f"(Excludes Sat, Sun, and Mon Canberra Day)")
    assert result == 5, f"Expected 5, got {result}"
    print("✓ PASSED")

    # Test 3: Range including a public holiday (Canberra Day - 2025-03-10)
    # 2025-03-07 (Fri) to 2025-03-11 (Tue) = 1 business day (Fri excluded, Mon is holiday, Tue included)
    # Actually: Fri + Tue = 2 business days
    result = calculate_business_days("2025-03-07T00:00:00Z", "2025-03-11T00:00:00Z")
    print(f"\nTest 3: Fri to Tue including Canberra Day (Mon)")
    print(f"2025-03-07 to 2025-03-11: {result} business days")
    print(f"(Excludes Sat, Sun, and Mon public holiday)")
    assert result == 2, f"Expected 2, got {result}"
    print("✓ PASSED")

    # Test 4: Christmas/New Year period
    # 2025-12-22 (Mon) to 2026-01-12 (Mon)
    # Dec 22 (Mon) = 1 business day
    # Dec 23-31 = NOT business days (Christmas period)
    # Jan 1-10 = NOT business days (Christmas period)
    # Jan 11 (Sun) = NOT business day
    # Jan 12 (Mon) = 1 business day
    # Total = 2 business days
    result = calculate_business_days("2025-12-22T00:00:00Z", "2026-01-12T00:00:00Z")
    print(f"\nTest 4: Christmas/New Year period")
    print(f"2025-12-22 to 2026-01-12: {result} business days")
    print(f"(Only Mon Dec 22 and Mon Jan 12 are business days)")
    assert result == 2, f"Expected 2, got {result}"
    print("✓ PASSED")

    # Test 5: Check specific dates
    print(f"\nTest 5: Specific date checks")

    # Saturday should not be a business day
    sat = datetime(2025, 3, 8)  # Saturday
    assert not is_business_day(sat), "Saturday should not be a business day"
    print(f"✓ 2025-03-08 (Saturday) is NOT a business day")

    # Sunday should not be a business day
    sun = datetime(2025, 3, 9)  # Sunday
    assert not is_business_day(sun), "Sunday should not be a business day"
    print(f"✓ 2025-03-09 (Sunday) is NOT a business day")

    # Canberra Day should not be a business day
    canberra_day = datetime(2025, 3, 10)  # Monday - Canberra Day
    assert not is_business_day(canberra_day), "Canberra Day should not be a business day"
    print(f"✓ 2025-03-10 (Canberra Day) is NOT a business day")

    # December 25 should not be a business day (Christmas period)
    christmas = datetime(2025, 12, 25)
    assert not is_business_day(christmas), "Dec 25 should not be a business day"
    print(f"✓ 2025-12-25 (Christmas Day) is NOT a business day")

    # January 5 should not be a business day (Christmas period)
    jan_5 = datetime(2026, 1, 5)  # Monday
    assert not is_business_day(jan_5), "Jan 5 should not be a business day (Christmas period)"
    print(f"✓ 2026-01-05 (Christmas period) is NOT a business day")

    # Regular Tuesday should be a business day
    regular_tuesday = datetime(2025, 3, 4)
    assert is_business_day(regular_tuesday), "Regular Tuesday should be a business day"
    print(f"✓ 2025-03-04 (Regular Tuesday) IS a business day")

    print("\n" + "=" * 50)
    print("All tests passed! ✓")
    print("=" * 50)

if __name__ == "__main__":
    test_business_days()
