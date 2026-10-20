"""Shared ARIMA email layout: logo header, readable body, one primary button and a brand footer.

Table-based with inline styles so it renders in Gmail, Outlook (including Word-based desktop
Outlook) and on phones. The website (ArimaHQ/aryan-portfolio, lib/email/layout.ts) uses the same
structure and hosts the logo; keep the two in step.
"""

import re
from dataclasses import dataclass, field
from html import escape

SITE_URL = "https://arimafinance.xyz"
LOGO_URL = f"{SITE_URL}/email/arima-logo.png"

# From the site's design tokens (--ink, --fg, --gold, --f-sans).
INK = "#010305"
GOLD = "#e9c070"
TEXT = "#14202b"
MUTED = "#5b6876"
PAGE = "#eef1f4"
FONT = "'Helvetica Neue',Helvetica,Arial,sans-serif"

FOOTER = {
    "en": {"brand": "ARIMA Finance", "alt": "ARIMA Finance", "fallback": "If the button does not work, open this link:"},
    "fa": {"brand": "آریما فایننس", "alt": "لوگوی آریما فایننس", "fallback": "اگر دکمه کار نکرد، این نشانی را در مرورگر باز کنید:"},
}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def single_line(value: str) -> str:
    """Strips control characters so text cannot add lines or headers."""
    return _CONTROL.sub(" ", value)


@dataclass(frozen=True, slots=True)
class EmailAction:
    label: str
    url: str


@dataclass(frozen=True, slots=True)
class EmailLayout:
    preheader: str
    heading: str
    paragraphs: list[str]
    rows: list[tuple[str, str]] = field(default_factory=list)
    action: EmailAction | None = None
    note: str | None = None
    locale: str = "en"


def render_html(layout: EmailLayout) -> str:
    rtl = layout.locale == "fa"
    direction = "rtl" if rtl else "ltr"
    align = "right" if rtl else "left"
    footer = FOOTER["fa" if rtl else "en"]

    paragraphs = "\n".join(
        f'<p style="margin:0 0 16px;font-family:{FONT};font-size:16px;line-height:26px;'
        f'color:{TEXT};text-align:{align}">{escape(text)}</p>'
        for text in layout.paragraphs
    )
    rows = ""
    if layout.rows:
        rows = (
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" '
            'style="margin:4px 0 20px;border-collapse:collapse">'
            + "".join(
                f'<tr><td width="38%" style="padding:9px 12px 9px 0;border-bottom:1px solid #e3e7eb;'
                f"font-family:{FONT};font-size:13px;line-height:20px;color:{MUTED};text-align:{align};"
                f'white-space:nowrap;vertical-align:top">{escape(label)}</td>'
                f'<td dir="auto" style="padding:9px 0;border-bottom:1px solid #e3e7eb;font-family:{FONT};'
                f"font-size:15px;line-height:22px;color:{TEXT};text-align:{align};word-break:break-word\">"
                f"{escape(single_line(value))}</td></tr>"
                for label, value in layout.rows
            )
            + "</table>"
        )
    button = ""
    if layout.action:
        url = escape(layout.action.url, quote=True)
        button = (
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="{align}" '
            f'style="margin:8px 0 24px"><tr><td bgcolor="{INK}" style="border-radius:6px;'
            f'border:1px solid {GOLD};mso-padding-alt:14px 28px"><a href="{url}" target="_blank" '
            f'style="display:inline-block;padding:14px 28px;font-family:{FONT};font-size:16px;'
            f'line-height:20px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:6px">'
            f"{escape(layout.action.label)}</a></td></tr></table>\n"
            f'<p style="clear:both;margin:0 0 16px;font-family:{FONT};font-size:13px;line-height:20px;'
            f'color:{MUTED};text-align:{align};word-break:break-all">{escape(footer["fallback"])}<br>'
            f'<a href="{url}" style="color:{TEXT}">{escape(layout.action.url)}</a></p>'
        )
    note = (
        f'<p style="margin:8px 0 0;font-family:{FONT};font-size:13px;line-height:20px;color:{MUTED};'
        f'text-align:{align}">{escape(layout.note)}</p>'
        if layout.note
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="{layout.locale}" dir="{direction}" xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{escape(layout.heading)}</title>
<!--[if mso]><style>table,td,p,a,h1{{font-family:Arial,sans-serif!important}}</style><![endif]-->
<style>@media (max-width:620px){{.arima-card{{width:100%!important}}.arima-pad{{padding-left:20px!important;padding-right:20px!important}}}}</style>
</head>
<body style="margin:0;padding:0;background:{PAGE};-webkit-text-size-adjust:100%">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent">{escape(layout.preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{PAGE}" style="background:{PAGE}">
<tr><td align="center" style="padding:24px 12px">
<!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0"><tr><td><![endif]-->
<table role="presentation" class="arima-card" width="600" cellpadding="0" cellspacing="0" border="0" dir="{direction}" style="width:600px;max-width:600px;background:#ffffff;border-radius:10px;overflow:hidden">
<tr><td align="center" bgcolor="{INK}" style="background:{INK};padding:28px 24px 24px">
<a href="{SITE_URL}" target="_blank"><img src="{LOGO_URL}" width="96" height="97" alt="{escape(footer["alt"], quote=True)}" style="display:block;width:96px;height:97px;border:0;outline:none;text-decoration:none;color:#ffffff;font-family:{FONT};font-size:16px"></a>
</td></tr>
<tr><td bgcolor="{GOLD}" style="height:3px;line-height:3px;font-size:0;background:{GOLD}">&nbsp;</td></tr>
<tr><td class="arima-pad" dir="{direction}" style="padding:32px 40px 24px;text-align:{align}">
<h1 style="margin:0 0 18px;font-family:{FONT};font-size:22px;line-height:30px;font-weight:bold;color:{INK};text-align:{align}">{escape(layout.heading)}</h1>
{paragraphs}
{rows}
{button}
{note}
</td></tr>
<tr><td class="arima-pad" bgcolor="{INK}" dir="{direction}" style="background:{INK};padding:20px 40px;text-align:{align}">
<p style="margin:0;font-family:{FONT};font-size:13px;line-height:20px;color:#eef8ff;text-align:{align}"><strong style="color:{GOLD}">{escape(footer["brand"])}</strong> &middot; <a href="{SITE_URL}" target="_blank" style="color:#eef8ff;text-decoration:underline">arimafinance.xyz</a></p>
</td></tr>
</table>
<!--[if mso]></td></tr></table><![endif]-->
</td></tr>
</table>
</body>
</html>"""


def render_text(layout: EmailLayout) -> str:
    """Plain-text alternative with the same content."""
    lines = [layout.heading, ""]
    for text in layout.paragraphs:
        lines += [text, ""]
    if layout.rows:
        lines += [f"{label}: {single_line(value)}" for label, value in layout.rows] + [""]
    if layout.action:
        lines += [f"{layout.action.label}: {layout.action.url}", ""]
    if layout.note:
        lines += [layout.note, ""]
    lines += ["--", f"{FOOTER['fa' if layout.locale == 'fa' else 'en']['brand']} · {SITE_URL}"]
    return "\n".join(lines) + "\n"
