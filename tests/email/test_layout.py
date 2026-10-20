from decimal import Decimal
from uuid import UUID

from app.email.layout import (
    LOGO_URL,
    EmailAction,
    EmailLayout,
    render_html,
    render_text,
)
from app.email.templates import (
    login_notification_email,
    password_reset_email,
    verification_email,
    withdrawal_received_email,
)


def test_every_template_uses_the_branded_layout_with_a_text_alternative() -> None:
    template = verification_email(recipient_name="Ada", verification_url="https://arimafinance.xyz/verify-email?token=t")
    assert template.subject == "Verify your Arima Executive OS email"
    assert f'src="{LOGO_URL}"' in template.html_body
    assert 'alt="ARIMA Finance"' in template.html_body
    assert 'href="https://arimafinance.xyz/verify-email?token=t"' in template.html_body
    assert "Verify email address: https://arimafinance.xyz/verify-email?token=t" in template.text_body
    assert "ARIMA Finance · https://arimafinance.xyz" in template.text_body


def test_visitor_text_is_escaped_and_kept_on_one_line() -> None:
    template = login_notification_email(recipient_name="<b>Eve</b>", ip_address="203.0.113.9", user_agent="X\nBcc: y@z")
    assert "&lt;b&gt;Eve&lt;/b&gt;" in template.html_body
    assert "<b>Eve</b>" not in template.html_body
    assert "Device: X Bcc: y@z" in template.text_body


def test_links_with_quotes_cannot_break_the_attribute() -> None:
    template = password_reset_email(recipient_name="Ada", reset_url='https://arimafinance.xyz/reset-password?token="x')
    assert 'href="https://arimafinance.xyz/reset-password?token=&quot;x"' in template.html_body


def test_persian_layout_reads_right_to_left() -> None:
    layout = EmailLayout(
        preheader="پیش‌نمایش", heading="بازیابی رمز", paragraphs=["سلام آرین،"],
        action=EmailAction("بازیابی رمز", "https://arimafinance.xyz/reset-password?token=t"), locale="fa",
    )
    html = render_html(layout)
    assert '<html lang="fa" dir="rtl"' in html
    assert "text-align:right" in html and "text-align:left" not in html
    assert 'alt="لوگوی آریما فایننس"' in html
    assert render_text(layout).endswith("آریما فایننس · https://arimafinance.xyz\n")


def test_detail_rows_mark_values_for_automatic_direction() -> None:
    template = withdrawal_received_email(
        recipient_name="آرین", request_id=UUID(int=1), amount=Decimal("0.5"), currency="ETH",
        masked_wallet="0x12…ab", network="ethereum", support_email="support@example.com",
    )
    assert '<td dir="auto"' in template.html_body
    assert "Request ID: 00000000-0000-0000-0000-000000000001" in template.text_body
