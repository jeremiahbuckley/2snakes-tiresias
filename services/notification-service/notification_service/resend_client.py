"""
Thin wrapper around the Resend Python SDK.

This module exists to:
  1. Centralize from-address + API-key configuration in one place.
  2. Run in a "dry run" mode for unit tests and local dev (when
     RESEND_API_KEY is unset): the outbound email is logged and a fake
     message id is returned instead of hitting the API.
  3. Keep the dispatcher free of provider-specific knowledge, so swapping
     Resend for Postmark or SendGrid later only requires touching this file.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from . import config

logger = logging.getLogger(__name__)

# The Resend SDK is imported lazily inside ``send_email`` so that importing
# this module (and thus the notification_service package) does not fail
# when the ``resend`` library is not installed — useful for unit tests.


@dataclass
class EmailMessage:
    """A single outbound email prepared for the provider."""

    to: str
    subject: str
    text: str
    html: str
    # Extra headers (e.g. List-Unsubscribe / List-Unsubscribe-Post). Resend
    # accepts these as a list of {"name": ..., "value": ...} dicts.
    headers: dict[str, str] = field(default_factory=dict)


def _from_address() -> str:
    """Render the RFC 5322 "Name <email>" From header."""
    name = config.RESEND_FROM_NAME.strip()
    email = config.RESEND_FROM_EMAIL.strip()
    if name:
        return f"{name} <{email}>"
    return email


async def send_email(message: EmailMessage) -> str:
    """
    Send a rendered email through Resend.

    Returns the provider message id on success (or a synthetic id in
    dry-run mode). Raises on hard provider errors so the caller can log
    and mark the delivery row failed.
    """
    if config.is_dry_run():
        fake_id = f"dryrun-{uuid.uuid4()}"
        logger.info(
            "resend_client dry-run send: to=%s subject=%r id=%s",
            message.to, message.subject, fake_id,
        )
        return fake_id

    # Import lazily so test environments without the SDK installed still
    # work — callers in dry-run mode never hit this branch.
    import resend  # type: ignore[import-not-found]

    resend.api_key = config.RESEND_API_KEY

    headers_list = [{"name": k, "value": v} for k, v in message.headers.items()]

    payload = {
        "from": _from_address(),
        "to": [message.to],
        "subject": message.subject,
        "html": message.html,
        "text": message.text,
    }
    if headers_list:
        payload["headers"] = headers_list

    # The SDK's ``.send`` is sync (HTTP under the hood); call it directly
    # — Resend responses land in ~200-400ms and the scheduler is fine
    # with that on the MVP volume we expect. If this becomes a bottleneck
    # we can push it onto a thread via asyncio.to_thread.
    response = resend.Emails.send(payload)
    message_id: Optional[str] = None
    if isinstance(response, dict):
        message_id = response.get("id")
    elif hasattr(response, "id"):
        message_id = getattr(response, "id")

    if not message_id:
        raise RuntimeError(
            f"Resend did not return a message id (response={response!r})"
        )
    logger.info(
        "resend_client sent email: to=%s subject=%r id=%s",
        message.to, message.subject, message_id,
    )
    return message_id
