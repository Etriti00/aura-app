"""
Aura — Delivery Engine
Email delivery via Resend API (primary) with SMTP fallback.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from utils.logger import get_logger

logger = get_logger("delivery_engine")


class DeliveryEngine:
    """
    Handles email delivery with primary (Resend) and fallback (SMTP) transports.
    Tracks daily send counts for rate limiting.
    """

    def __init__(self):
        self._resend_key = None
        self._smtp_config = None
        self._daily_count = 0
        self._max_daily = 100
        self.rag_engine = None  # Optional RAGEngine for storing sent emails

    def configure_resend(self, api_key: str):
        """Set Resend API key."""
        self._resend_key = api_key

    def configure_smtp(self, host: str, port: int, username: str, password: str, use_tls: bool = True):
        """Set SMTP fallback configuration."""
        self._smtp_config = {
            "host": host,
            "port": port,
            "username": username,
            "password": password,
            "use_tls": use_tls,
        }

    def set_daily_limit(self, limit: int):
        """Set the daily email send limit."""
        self._max_daily = limit

    def reset_daily_count(self):
        """Reset the daily send counter (call at midnight)."""
        self._daily_count = 0

    @property
    def daily_remaining(self) -> int:
        return max(0, self._max_daily - self._daily_count)

    @property
    def daily_count(self) -> int:
        return self._daily_count

    def send_email(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        body: str,
        from_name: str = "",
    ) -> dict:
        """
        Send an email. Tries Resend first, falls back to SMTP.

        Returns:
            dict with keys: success (bool), method (str), error (str or None), message_id (str or None)
        """
        # Rate limit check
        if self._daily_count >= self._max_daily:
            return {
                "success": False,
                "method": "none",
                "error": f"Daily send limit of {self._max_daily} reached.",
                "message_id": None,
            }

        # Try Resend first
        if self._resend_key:
            result = self._send_via_resend(to_email, from_email, subject, body, from_name)
            if result["success"]:
                self._daily_count += 1
                self._store_in_rag(subject, body)
                return result
            logger.warning(f"Resend failed: {result['error']}. Trying SMTP fallback.")

        # Fallback to SMTP
        if self._smtp_config:
            result = self._send_via_smtp(to_email, from_email, subject, body, from_name)
            if result["success"]:
                self._daily_count += 1
                self._store_in_rag(subject, body)
                return result

        return {
            "success": False,
            "method": "none",
            "error": "No delivery method available. Configure Resend or SMTP in Settings.",
            "message_id": None,
        }

    def _store_in_rag(self, subject: str, body: str):
        """Store a successfully sent email in RAG memory."""
        if self.rag_engine:
            try:
                self.rag_engine.store_successful_email(
                    lead_id=None, subject=subject, body=body, reply_received=False
                )
            except Exception as e:
                logger.warning(f"Failed to store email in RAG: {e}")

    def _send_via_resend(
        self, to_email: str, from_email: str, subject: str, body: str, from_name: str
    ) -> dict:
        """Send email using Resend API."""
        try:
            import resend
            resend.api_key = self._resend_key

            from_str = f"{from_name} <{from_email}>" if from_name else from_email

            email = resend.Emails.send({
                "from": from_str,
                "to": [to_email],
                "subject": subject,
                "text": body,
            })

            message_id = email.get("id", "unknown") if isinstance(email, dict) else str(email)
            logger.info(f"Email sent via Resend to {to_email} (id: {message_id})")
            return {
                "success": True,
                "method": "resend",
                "error": None,
                "message_id": message_id,
            }
        except Exception as e:
            logger.error(f"Resend delivery failed: {e}")
            return {
                "success": False,
                "method": "resend",
                "error": str(e),
                "message_id": None,
            }

    def _send_via_smtp(
        self, to_email: str, from_email: str, subject: str, body: str, from_name: str
    ) -> dict:
        """Send email using SMTP fallback."""
        try:
            cfg = self._smtp_config
            msg = MIMEMultipart()
            msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            if cfg["use_tls"]:
                server = smtplib.SMTP(cfg["host"], cfg["port"])
                server.starttls()
            else:
                server = smtplib.SMTP(cfg["host"], cfg["port"])

            server.login(cfg["username"], cfg["password"])
            server.sendmail(from_email, to_email, msg.as_string())
            server.quit()

            logger.info(f"Email sent via SMTP to {to_email}")
            return {
                "success": True,
                "method": "smtp",
                "error": None,
                "message_id": None,
            }
        except Exception as e:
            logger.error(f"SMTP delivery failed: {e}")
            return {
                "success": False,
                "method": "smtp",
                "error": str(e),
                "message_id": None,
            }

    def send_with_screenshot(
        self,
        to_email: str,
        from_email: str,
        subject: str,
        body: str,
        screenshot_path: str,
        from_name: str = "",
    ) -> dict:
        """
        Send an email with an inline website screenshot.
        Uses multipart/related with CID for inline image embedding.
        Falls back to plain send if screenshot can't be attached.
        """
        import os
        if not screenshot_path or not os.path.exists(screenshot_path):
            return self.send_email(to_email, from_email, subject, body, from_name)

        # Rate limit check
        if self._daily_count >= self._max_daily:
            return {
                "success": False,
                "method": "none",
                "error": f"Daily send limit of {self._max_daily} reached.",
                "message_id": None,
            }

        try:
            from email.mime.image import MIMEImage

            # Build multipart/related message
            msg_root = MIMEMultipart("related")
            msg_root["From"] = f"{from_name} <{from_email}>" if from_name else from_email
            msg_root["To"] = to_email
            msg_root["Subject"] = subject

            # HTML body with inline image
            html_body = f"""<html><body>
<p>{body.replace(chr(10), '<br>')}</p>
<br>
<p><strong>Here's what your competitors' web presence looks like:</strong></p>
<img src="cid:screenshot_cid" style="max-width:600px; border:1px solid #ddd; border-radius:8px;">
</body></html>"""

            msg_alt = MIMEMultipart("alternative")
            msg_alt.attach(MIMEText(body, "plain", "utf-8"))
            msg_alt.attach(MIMEText(html_body, "html", "utf-8"))
            msg_root.attach(msg_alt)

            # Attach screenshot as inline image
            with open(screenshot_path, "rb") as f:
                img = MIMEImage(f.read())
            img.add_header("Content-ID", "<screenshot_cid>")
            img.add_header("Content-Disposition", "inline", filename="website.png")
            msg_root.attach(img)

            # Send via Resend (as HTML) or SMTP
            if self._resend_key:
                try:
                    import resend
                    resend.api_key = self._resend_key
                    from_str = f"{from_name} <{from_email}>" if from_name else from_email
                    email_resp = resend.Emails.send({
                        "from": from_str,
                        "to": [to_email],
                        "subject": subject,
                        "html": html_body,
                    })
                    message_id = email_resp.get("id", "unknown") if isinstance(email_resp, dict) else str(email_resp)
                    self._daily_count += 1
                    logger.info(f"Screenshot email sent via Resend to {to_email}")
                    return {"success": True, "method": "resend", "error": None, "message_id": message_id}
                except Exception as e:
                    logger.warning(f"Resend screenshot email failed: {e}")

            # Fallback: SMTP with full MIME attachment
            if self._smtp_config:
                try:
                    cfg = self._smtp_config
                    if cfg["use_tls"]:
                        server = smtplib.SMTP(cfg["host"], cfg["port"])
                        server.starttls()
                    else:
                        server = smtplib.SMTP(cfg["host"], cfg["port"])
                    server.login(cfg["username"], cfg["password"])
                    server.sendmail(from_email, to_email, msg_root.as_string())
                    server.quit()
                    self._daily_count += 1
                    logger.info(f"Screenshot email sent via SMTP to {to_email}")
                    return {"success": True, "method": "smtp", "error": None, "message_id": None}
                except Exception as e:
                    logger.warning(f"SMTP screenshot email failed: {e}")

            return {"success": False, "method": "none", "error": "No delivery method available", "message_id": None}
        except Exception as e:
            logger.error(f"Screenshot email failed: {e}")
            return self.send_email(to_email, from_email, subject, body, from_name)
