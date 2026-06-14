import smtplib
import uuid
from datetime import datetime
from email import policy
from email.message import EmailMessage
from pathlib import Path
from threading import Thread


def _clean_header(value: str | None) -> str:
    return (value or "").replace("\r", " ").replace("\n", " ").strip()


def send_email(
    app, to_email: str, subject: str, body: str, reply_to: str | None = None
):
    host = _clean_header(app.config.get("SMTP_HOST"))
    sender = (
        _clean_header(app.config.get("MAIL_FROM"))
        or _clean_header(app.config.get("SMTP_USER"))
        or "no-reply@localhost"
    )
    cleaned_to_email = _clean_header(to_email) or sender
    cleaned_subject = _clean_header(subject or "Notification")
    cleaned_reply_to = _clean_header(reply_to) or None

    message = EmailMessage()
    message["Subject"] = cleaned_subject
    message["From"] = sender
    message["To"] = cleaned_to_email
    if cleaned_reply_to:
        message["Reply-To"] = cleaned_reply_to
    message.set_content(body)

    if not host:
        if not app.config.get("EMAIL_FILE_FALLBACK", False):
            raise RuntimeError("SMTP_HOST is not configured.")
        outbox = Path(app.instance_path) / "outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        dump_file = outbox / f"{timestamp}_{uuid.uuid4().hex}.eml"
        dump_file.write_bytes(message.as_bytes(policy=policy.default))
        return

    port = int(app.config.get("SMTP_PORT", 587))
    username = app.config.get("SMTP_USER")
    password = app.config.get("SMTP_PASSWORD")
    use_tls = app.config.get("SMTP_USE_TLS", True)
    use_ssl = app.config.get("SMTP_USE_SSL", False)
    smtp_client = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP

    with smtp_client(host, port, timeout=8) as server:
        if not use_ssl:
            server.ehlo()
        if use_tls and not use_ssl:
            server.starttls()
            server.ehlo()
        if username and password:
            server.login(username, password)
        server.send_message(message)


def send_email_async(
    app,
    to_email: str,
    subject: str,
    body: str,
    reply_to: str | None = None,
):
    def worker():
        try:
            send_email(app, to_email, subject, body, reply_to=reply_to)
        except Exception:
            app.logger.exception(
                "Background email send failed for subject=%s recipient=%s",
                subject,
                to_email,
            )

    Thread(target=worker, daemon=True).start()
