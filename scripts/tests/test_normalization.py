"""Tests for normalization.py"""
import pytest
from scripts.normalization import normalize_determination


class TestNormalizeDetermination:
    """Test suite for normalize_determination function."""

    def test_normalize_approved(self):
        """Test normalization of 'Approved' determinations."""
        assert normalize_determination("Approved") == "Approved"
        assert normalize_determination("approved") == "Approved"
        assert normalize_determination("ACCC Determination Approved") == "Approved"
        assert normalize_determination("ACCC DeterminationApproved") == "Approved"

    def test_normalize_not_approved(self):
        """Test normalization of 'Not approved' determinations."""
        # Critical: "Not approved" must be normalized correctly, not as "Approved"
        assert normalize_determination("Not approved") == "Not approved"
        assert normalize_determination("not approved") == "Not approved"
        assert normalize_determination("ACCC Determination Not approved") == "Not approved"

    def test_normalize_declined(self):
        """Test normalization of 'Declined' determinations."""
        assert normalize_determination("Declined") == "Declined"
        assert normalize_determination("declined") == "Declined"
        assert normalize_determination("ACCC Determination Declined") == "Declined"

    def test_normalize_not_opposed(self):
        """Test normalization of 'Not opposed' determinations."""
        assert normalize_determination("Not opposed") == "Not opposed"
        assert normalize_determination("not opposed") == "Not opposed"
        assert normalize_determination("ACCC Determination Not opposed") == "Not opposed"

    def test_normalize_empty(self):
        """Test normalization of empty/None values."""
        assert normalize_determination(None) is None
        assert normalize_determination("") is None
        # Whitespace-only string returns empty string after strip
        result = normalize_determination("   ")
        assert result is None or result == ""

    def test_normalize_unknown(self):
        """Test normalization of unknown determination values."""
        # Unknown values should be returned as-is after prefix removal
        assert normalize_determination("Unknown Status") == "Unknown Status"
        assert normalize_determination("ACCC Determination Pending") == "Pending"

    def test_order_matters_not_approved_before_approved(self):
        """Verify that 'Not approved' is checked before 'Approved' to avoid substring bugs."""
        # This is a critical test to ensure the order of checks is correct
        test_cases = [
            ("Not approved", "Not approved"),
            ("not approved", "Not approved"),
            ("This is Not approved", "Not approved"),
            ("Approved", "Approved"),
            ("approved", "Approved"),
        ]
        for input_val, expected in test_cases:
            assert normalize_determination(input_val) == expected
