"""Unit tests for validation service.

No database, no HTTP, no Celery.
"""
from __future__ import annotations

import pytest

from app.schemas.generation_job import RecipientIn
from app.services.validation_service import (
    EC_INVALID_EMAIL,
    EC_NAME_EMPTY,
    EC_NAME_TOO_LONG,
    validate_recipients,
)


def _r(name: str, email: str | None = None) -> RecipientIn:
    """Build a RecipientIn bypassing Pydantic validation.

    This lets us test the *service-level* validation logic (which handles
    invalid recipients gracefully rather than rejecting the whole request).
    """
    return RecipientIn.model_construct(name=name, email=email)



class TestValidateRecipients:
    def test_all_valid(self):
        recipients = [_r("Alice"), _r("Bob", "bob@example.com")]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 2
        assert len(failed) == 0

    def test_empty_name_fails(self):
        recipients = [_r("   ")]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 0
        assert len(failed) == 1
        assert failed[0].error_code == EC_NAME_EMPTY

    def test_name_too_long_fails(self):
        recipients = [_r("A" * 121)]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 0
        assert len(failed) == 1
        assert failed[0].error_code == EC_NAME_TOO_LONG

    def test_name_exactly_120_chars_passes(self):
        recipients = [_r("A" * 120)]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 1
        assert len(failed) == 0

    def test_invalid_email_fails(self):
        recipients = [_r("Alice", "not-an-email")]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 0
        assert len(failed) == 1
        assert failed[0].error_code == EC_INVALID_EMAIL

    def test_missing_email_passes(self):
        """Email is optional."""
        recipients = [_r("Bob")]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 1
        assert valid[0].email is None

    def test_sequence_numbers_assigned(self):
        recipients = [_r("Alice"), _r("  "), _r("Bob")]
        valid, failed = validate_recipients(recipients)
        valid_seqs = {v.sequence_number for v in valid}
        failed_seqs = {f.sequence_number for f in failed}
        assert valid_seqs == {1, 3}
        assert failed_seqs == {2}

    def test_duplicate_names_both_valid(self):
        """Same name is allowed for different participants."""
        recipients = [_r("Alice"), _r("Alice")]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 2
        assert len(failed) == 0

    def test_whitespace_stripped_from_name(self):
        recipients = [_r("  Alice  ")]
        valid, failed = validate_recipients(recipients)
        assert valid[0].name == "Alice"

    def test_mixed_batch(self):
        recipients = [
            _r("Alice"),
            _r("", "bad"),
            _r("B" * 121),
            _r("Charlie", "charlie@example.com"),
        ]
        valid, failed = validate_recipients(recipients)
        assert len(valid) == 2
        assert len(failed) == 2
