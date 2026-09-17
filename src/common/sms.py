"""Shared SMS notification client - USMS Ghana (https://usmsgh.com).

Confirmed contract: POST {USMS_BASE_URL}/api/sms/send, Bearer token auth,
form body {recipient, sender_id, message}.

Notifications are best-effort by design: send_sms() never raises. A
downed SMS gateway or a bad sender_id must never fail a payment
confirmation or a webhook handler - the money movement already happened
(or didn't) independently of whether the user got told about it. Callers
that care can inspect the bool return; nothing else needs to.
"""

import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


def _normalize_ghana_number(phone: str) -> str:
    """USMS expects international format with no leading '+' (e.g. 233XXXXXXXXX).
    Users register with whatever format they type - normalize the common
    Ghanaian local format (0XXXXXXXXX) instead of assuming it's already right."""
    digits = phone.strip().replace(" ", "").replace("-", "")
    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "233" + digits[1:]
    return digits


async def send_sms(to: str, message: str) -> bool:
    if not settings.USMS_TOKEN or not settings.USMS_SENDER_ID:
        logger.warning("SMS not sent (USMS credentials not configured): %s", message)
        return False

    recipient = _normalize_ghana_number(to)
    try:
        async with httpx.AsyncClient(base_url=settings.USMS_BASE_URL, timeout=10.0) as client:
            resp = await client.post(
                "/api/sms/send",
                headers={"Authorization": f"Bearer {settings.USMS_TOKEN}"},
                data={
                    "recipient": recipient,
                    "sender_id": settings.USMS_SENDER_ID,
                    "message": message,
                },
            )
        if resp.status_code >= 400:
            logger.warning("USMS send failed (%s): %s", resp.status_code, resp.text)
            return False
        return True
    except httpx.HTTPError as e:
        logger.warning("USMS send failed: %s", e)
        return False
