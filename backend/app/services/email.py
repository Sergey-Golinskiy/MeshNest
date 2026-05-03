"""SMTP email service.

Если `SMTP_HOST` пустой в env — отправка no-op (только лог). Это позволяет
работать без SMTP в dev / при первичной установке когда invite ссылки
просто копируются вручную из админки.
"""
from __future__ import annotations

from email.message import EmailMessage

import aiosmtplib
import structlog

from app.config import settings

log = structlog.get_logger()


def _is_configured() -> bool:
    return bool(settings.smtp_host)


async def send_email(*, to: str, subject: str, html: str, text: str | None = None) -> bool:
    """Возвращает True если отправлено (или no-op в dev). False — если SMTP не сконфигурирован
    но кто-то всё равно хочет именно отправить (caller сам решает что делать)."""
    if not _is_configured():
        log.info("email.skipped_no_smtp", to=to, subject=subject)
        return False

    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text or _strip_tags(html))
    msg.add_alternative(html, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password.get_secret_value() or None,
            start_tls=settings.smtp_use_tls,
        )
        log.info("email.sent", to=to, subject=subject)
        return True
    except Exception as exc:
        log.error("email.failed", to=to, subject=subject, error=str(exc))
        return False


def _strip_tags(html: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", html)


# ---------- ready-made templates ----------

async def send_invite_email(*, to: str, invite_url: str, role: str, expires_at: str) -> bool:
    subject = f"You're invited to MeshNest ({role})"
    html = f"""
    <div style="font-family:Inter,system-ui,sans-serif;max-width:520px;margin:0 auto;padding:24px;color:#0a0a0a">
      <h1 style="font-size:20px;margin:0 0 16px">Welcome to MeshNest</h1>
      <p>You've been invited to join MeshNest as <strong>{role}</strong>.</p>
      <p>Use the link below to set up your account. The invite expires {expires_at}.</p>
      <p style="margin:24px 0">
        <a href="{invite_url}"
           style="background:#2563eb;color:#fff;padding:10px 20px;border-radius:6px;
                  text-decoration:none;font-weight:600">
          Accept invitation
        </a>
      </p>
      <p style="color:#71717a;font-size:13px">If the button doesn't work, copy and paste this URL:</p>
      <p style="word-break:break-all"><code>{invite_url}</code></p>
    </div>
    """
    return await send_email(to=to, subject=subject, html=html)
