import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger("autorewier.smtp")


@dataclass
class DeliveryResult:
    delivered: bool
    provider: str
    message: str
    dev_code: str | None = None


class VerificationEmailProvider:
    async def send_code(self, target_email: str, code: str) -> DeliveryResult:
        raise NotImplementedError

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        raise NotImplementedError


class ResendVerificationEmailProvider(VerificationEmailProvider):
    def _from_addr(self) -> str:
        name = settings.smtp_sender_name or "ПОДКАПОТ"
        # Use verified domain sender; fall back to onboarding address for testing
        sender = settings.smtp_sender_email.strip() or "onboarding@resend.dev"
        return f"{name} <{sender}>"

    async def send_code(self, target_email: str, code: str) -> DeliveryResult:
        try:
            import resend
            resend.api_key = settings.resend_api_key
            params = {
                "from": self._from_addr(),
                "to": [target_email],
                "subject": "Код подтверждения ПОДКАПОТ",
                "html": f"""
<!DOCTYPE html>
<html>
<body style="background:#050810;color:#f8fafc;font-family:Inter,sans-serif;padding:40px">
  <h1 style="color:#3fd0ff;font-family:sans-serif">ПОДКАПОТ</h1>
  <p style="font-size:18px">Ваш код подтверждения:</p>
  <div style="background:#0f172a;border:1px solid #3fd0ff;border-radius:12px;padding:24px;text-align:center;margin:24px 0">
    <span style="font-size:48px;font-weight:800;letter-spacing:12px;color:#3fd0ff">{code}</span>
  </div>
  <p style="color:#94a3b8">Код действует {settings.verification_code_ttl_minutes} минут.</p>
  <p style="color:#64748b;font-size:12px">Если вы не регистрировались на ПОДКАПОТ — проигнорируйте это письмо.</p>
</body>
</html>""",
            }
            resend.Emails.send(params)
            return DeliveryResult(delivered=True, provider="resend",
                                  message="Код подтверждения отправлен на email.")
        except Exception as e:
            log.error("Resend send_code failed: %s", e, exc_info=True)
            return DeliveryResult(delivered=False, provider="resend",
                                  message=f"Resend delivery failed: {e}")

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        try:
            import resend
            resend.api_key = settings.resend_api_key
            params = {
                "from": self._from_addr(),
                "to": [target_email],
                "subject": "Восстановление пароля ПОДКАПОТ",
                "html": f"""
<!DOCTYPE html>
<html>
<body style="background:#050810;color:#f8fafc;font-family:Inter,sans-serif;padding:40px">
  <h1 style="color:#3fd0ff;font-family:sans-serif">ПОДКАПОТ</h1>
  <p style="font-size:18px">Вы запросили восстановление пароля.</p>
  <div style="margin:24px 0;text-align:center">
    <a href="{reset_link}"
       style="background:#3fd0ff;color:#050810;padding:14px 32px;border-radius:8px;
              font-weight:700;text-decoration:none;font-size:16px">
      Сбросить пароль
    </a>
  </div>
  <p style="color:#94a3b8">Ссылка действительна 1 час.</p>
  <p style="color:#64748b;font-size:12px">Если вы не запрашивали сброс — проигнорируйте это письмо.</p>
</body>
</html>""",
            }
            resend.Emails.send(params)
            return DeliveryResult(delivered=True, provider="resend",
                                  message="Ссылка восстановления пароля отправлена на email.")
        except Exception as e:
            log.error("Resend send_reset_link failed: %s", e, exc_info=True)
            return DeliveryResult(delivered=False, provider="resend",
                                  message=f"Resend delivery failed: {e}")


class SmtpVerificationEmailProvider(VerificationEmailProvider):
    def _smtp_configured(self) -> bool:
        return bool(settings.smtp_host.strip() and settings.smtp_sender_email.strip())

    def _make_from(self) -> str:
        if settings.smtp_sender_name.strip():
            return f"{settings.smtp_sender_name} <{settings.smtp_sender_email}>"
        return settings.smtp_sender_email

    def _send_msg(self, msg: EmailMessage) -> None:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username.strip():
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)

    async def send_code(self, target_email: str, code: str) -> DeliveryResult:
        if not self._smtp_configured():
            return DeliveryResult(delivered=False, provider="smtp", message="SMTP not configured")
        msg = EmailMessage()
        msg["Subject"] = "Код подтверждения ПОДКАПОТ"
        msg["From"] = self._make_from()
        msg["To"] = target_email
        msg.set_content(
            f"Ваш код подтверждения ПОДКАПОТ:\n\n{code}\n\n"
            f"Код действует {settings.verification_code_ttl_minutes} минут."
        )
        try:
            self._send_msg(msg)
            return DeliveryResult(delivered=True, provider="smtp",
                                  message="Код подтверждения отправлен на email.")
        except Exception as e:
            log.error("SMTP send_code failed: %s", e, exc_info=True)
            return DeliveryResult(delivered=False, provider="smtp",
                                  message=f"SMTP delivery failed: {e}")

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        if not self._smtp_configured():
            return DeliveryResult(delivered=False, provider="smtp", message="SMTP not configured")
        msg = EmailMessage()
        msg["Subject"] = "Восстановление пароля ПОДКАПОТ"
        msg["From"] = self._make_from()
        msg["To"] = target_email
        msg.set_content(
            f"Ссылка для сброса пароля ПОДКАПОТ:\n{reset_link}\n\n"
            "Ссылка действительна 1 час."
        )
        try:
            self._send_msg(msg)
            return DeliveryResult(delivered=True, provider="smtp",
                                  message="Ссылка восстановления пароля отправлена на email.")
        except Exception as e:
            log.error("SMTP send_reset_link failed: %s", e, exc_info=True)
            return DeliveryResult(delivered=False, provider="smtp",
                                  message=f"SMTP delivery failed: {e}")


class MockVerificationEmailProvider(VerificationEmailProvider):
    async def send_code(self, target_email: str, code: str) -> DeliveryResult:
        if settings.is_production:
            return DeliveryResult(delivered=False, provider="mock",
                                  message="Mock delivery is disabled in production")
        return DeliveryResult(delivered=True, provider="mock",
                              message="Код отправлен в dev fallback.", dev_code=code)

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        if settings.is_production:
            return DeliveryResult(delivered=False, provider="mock",
                                  message="Mock delivery is disabled in production")
        return DeliveryResult(delivered=True, provider="mock",
                              message=f"Ссылка сброса (dev): {reset_link}")


def get_verification_email_provider() -> VerificationEmailProvider:
    if settings.resend_api_key.strip():
        return ResendVerificationEmailProvider()
    if settings.smtp_host.strip() and settings.smtp_sender_email.strip():
        return SmtpVerificationEmailProvider()
    return MockVerificationEmailProvider()
