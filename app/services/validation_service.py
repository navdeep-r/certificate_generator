"""Validation service — recipient business rules.

This module converts raw RecipientIn Pydantic models into
(valid_recipients, failed_records) without touching the database.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.schemas.generation_job import RecipientIn

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Error codes
EC_INVALID_RECIPIENT = "INVALID_RECIPIENT"
EC_INVALID_EMAIL = "INVALID_EMAIL"
EC_NAME_TOO_LONG = "NAME_TOO_LONG"
EC_NAME_EMPTY = "NAME_EMPTY"


@dataclass
class ValidatedRecipient:
    sequence_number: int
    name: str
    email: Optional[str]


@dataclass
class FailedRecipient:
    sequence_number: int
    name: str
    email: Optional[str]
    error_code: str
    error_message: str


def validate_recipients(
    recipients: list[RecipientIn],
) -> tuple[list[ValidatedRecipient], list[FailedRecipient]]:
    """Validate each recipient independently.

    Returns:
        (valid_list, failed_list)
    """
    valid: list[ValidatedRecipient] = []
    failed: list[FailedRecipient] = []

    for seq, recipient in enumerate(recipients, start=1):
        name = recipient.name.strip() if recipient.name else ""
        email_raw = str(recipient.email) if recipient.email else None

        # Name checks
        if not name:
            failed.append(
                FailedRecipient(
                    sequence_number=seq,
                    name=name,
                    email=email_raw,
                    error_code=EC_NAME_EMPTY,
                    error_message="Recipient name cannot be blank.",
                )
            )
            continue

        if len(name) > 120:
            failed.append(
                FailedRecipient(
                    sequence_number=seq,
                    name=name,
                    email=email_raw,
                    error_code=EC_NAME_TOO_LONG,
                    error_message=f"Recipient name exceeds 120 characters (got {len(name)}).",
                )
            )
            continue

        # Email check (optional field — only validate when present)
        if email_raw and not _EMAIL_RE.match(email_raw):
            failed.append(
                FailedRecipient(
                    sequence_number=seq,
                    name=name,
                    email=email_raw,
                    error_code=EC_INVALID_EMAIL,
                    error_message="Email address is not valid.",
                )
            )
            continue

        valid.append(ValidatedRecipient(sequence_number=seq, name=name, email=email_raw))

    return valid, failed
