from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode
from uuid import UUID

from app.email.layout import (
    EmailAction,
    EmailLayout,
    render_html,
    render_text,
    single_line,
)


@dataclass(frozen=True, slots=True)
class EmailTemplate:
    subject: str
    text_body: str
    html_body: str


def _template(subject: str, layout: EmailLayout) -> EmailTemplate:
    return EmailTemplate(subject=subject, text_body=render_text(layout), html_body=render_html(layout))


def withdrawal_intake_email(
    *,
    full_name: str,
    amount_eth: Decimal,
    wallet_address: str,
    network: str,
    note: str | None,
    account_email: str,
    workspace_reference: str,
    submitted_at: str,
) -> EmailTemplate:
    return _template(
        f"Withdrawal request intake: {single_line(full_name)}",
        EmailLayout(
            preheader="New withdrawal request intake submission (no funds moved).",
            heading="New withdrawal request intake submission",
            paragraphs=[
                "New withdrawal request intake submission (no funds moved).",
                "No funds were moved, reserved, or recorded.",
            ],
            rows=[
                ("Full name", full_name),
                ("Amount (ETH)", str(amount_eth)),
                ("Wallet address", wallet_address),
                ("Network", network),
                ("Note", note or "No note provided"),
                ("Account email", account_email),
                ("Workspace", workspace_reference),
                ("Submitted at", submitted_at),
            ],
            note="The customer was told that the team will respond within 48 hours.",
        ),
    )


def verification_email(
    *,
    recipient_name: str,
    verification_url: str,
) -> EmailTemplate:
    return _template(
        "Verify your Arima Executive OS email",
        EmailLayout(
            preheader="Verify your email address to activate your account.",
            heading="Verify your email address",
            paragraphs=[
                f"Hello {recipient_name},",
                "Verify your email address to activate your Arima Executive OS account.",
            ],
            action=EmailAction("Verify email address", verification_url),
            note="If you did not create this account, you can ignore this email.",
        ),
    )


def password_reset_email(
    *,
    recipient_name: str,
    reset_url: str,
) -> EmailTemplate:
    return _template(
        "Reset your Arima Executive OS password",
        EmailLayout(
            preheader="Use this secure link to reset your password.",
            heading="Reset your password",
            paragraphs=[f"Hello {recipient_name},", "Use this secure link to reset your password."],
            action=EmailAction("Reset password", reset_url),
            note="If you did not request this change, secure your account and contact support.",
        ),
    )


def email_change_email(
    *,
    recipient_name: str,
    change_url: str,
) -> EmailTemplate:
    return _template(
        "Confirm your new Arima Executive OS email",
        EmailLayout(
            preheader="Confirm this email address for your account.",
            heading="Confirm your new email address",
            paragraphs=[
                f"Hello {recipient_name},",
                "Confirm this email address for your Arima Executive OS account.",
            ],
            action=EmailAction("Confirm email change", change_url),
            note="If you did not request this change, secure your account and contact support.",
        ),
    )


def welcome_email(*, recipient_name: str) -> EmailTemplate:
    return _template(
        "Welcome to Arima Executive OS",
        EmailLayout(
            preheader="Your Arima Executive OS workspace is ready.",
            heading=f"Welcome {recipient_name}",
            paragraphs=["Your Arima Executive OS workspace is ready."],
        ),
    )


def login_notification_email(
    *,
    recipient_name: str,
    ip_address: str | None,
    user_agent: str | None,
) -> EmailTemplate:
    location = ip_address or "an unknown network"
    device = user_agent or "an unknown device"
    return _template(
        "New sign-in to Arima Executive OS",
        EmailLayout(
            preheader="A sign-in to your account was detected.",
            heading="New sign-in to your account",
            paragraphs=[
                f"Hello {recipient_name},",
                f"A sign-in to your Arima Executive OS account was detected from {location} using {device}.",
            ],
            rows=[("Network", location), ("Device", device)],
            note="If this was not you, reset your password immediately.",
        ),
    )


def security_alert_email(
    *,
    recipient_name: str,
    event: str,
) -> EmailTemplate:
    return _template(
        "Security alert for Arima Executive OS",
        EmailLayout(
            preheader=f"Security event: {single_line(event)}.",
            heading="Security alert",
            paragraphs=[f"Hello {recipient_name},", f"Security event: {event}."],
            note="If you did not initiate this activity, reset your password and contact support.",
        ),
    )


def withdrawal_received_email(
    *, recipient_name: str, request_id: UUID, amount: Decimal,
    currency: str, masked_wallet: str, network: str, support_email: str,
) -> EmailTemplate:
    return _template(
        "Withdrawal request received",
        EmailLayout(
            preheader="Your withdrawal request has been received and is under review.",
            heading="Withdrawal request received",
            paragraphs=[
                f"Hello {recipient_name},",
                "Your withdrawal request has been received and is under review.",
                f"Our team will review it and communicate within 24 hours. Support: {support_email}",
            ],
            rows=[
                ("Request ID", str(request_id)),
                ("Amount", f"{amount} {currency}"),
                ("Destination", masked_wallet),
                ("Network", network),
            ],
            note="This does not confirm completion.",
        ),
    )


def link(
    base_url: str,
    path: str,
    token: str,
    *,
    parameters: dict[str, str] | None = None,
) -> str:
    query = {"token": token, **(parameters or {})}
    return f"{base_url.rstrip('/')}{path}?{urlencode(query)}"
