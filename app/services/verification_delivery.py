import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings


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
            return DeliveryResult(
                delivered=False,
                provider="smtp",
                message="SMTP not configured",
            )
        msg = EmailMessage()
        msg["Subject"] = "Код подтверждения ПОДКАПОТ"
        msg["From"] = self._make_from()
        msg["To"] = target_email
        msg.set_content(
            "Ваш код подтверждения AutoRewier:\n\n"
            f"{code}\n\n"
            f"Код действует {settings.verification_code_ttl_minutes} минут."
        )
        msg.add_alternative(f"""
<!DOCTYPE html>
<html>
<body style="background:#050810;color:#f8fafc;font-family:Inter,sans-serif;padding:40px">
  <h1 style="color:#3fd0ff;font-family:sans-serif">ПОДКАПОТ</h1>
  <p style="font-size:18px">Ваш код подтверждения:</p>
  <div style="background:#0f172a;border:1px solid #0ea5e9;border-radius:12px;padding:24px;text-align:center;margin:24px 0">
    <span style="font-size:48px;font-weight:800;letter-spacing:12px;color:#0ea5e9">{code}</span>
  </div>
  <p style="color:#94a3b8">Код действует {settings.verification_code_ttl_minutes} минут.</p>
  <p style="color:#64748b;font-size:12px">Если вы не регистрировались на ПОДКАПОТ — проигнорируйте это письмо.</p>
</body>
</html>
""", subtype='html')
        try:
            self._send_msg(msg)
            return DeliveryResult(
                delivered=True,
                provider="smtp",
                message="Код подтверждения отправлен на email.",
            )
        except Exception:
            return DeliveryResult(
                delivered=False,
                provider="smtp",
                message="SMTP delivery failed",
            )

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        if not self._smtp_configured():
            return DeliveryResult(
                delivered=False,
                provider="smtp",
                message="SMTP not configured",
            )
        msg = EmailMessage()
        msg["Subject"] = "Восстановление пароля ПОДКАПОТ"
        msg["From"] = self._make_from()
        msg["To"] = target_email
        msg.set_content(
            "Вы запросили восстановление пароля AutoRewier.\n\n"
            f"Перейдите по ссылке для сброса пароля:\n{reset_link}\n\n"
            "Ссылка действительна 1 час. Если вы не запрашивали сброс — игнорируйте письмо."
        )
        try:
            self._send_msg(msg)
            return DeliveryResult(
                delivered=True,
                provider="smtp",
                message="Ссылка восстановления пароля отправлена на email.",
            )
        except Exception:
            return DeliveryResult(
                delivered=False,
                provider="smtp",
                message="SMTP delivery failed",
            )


class MockVerificationEmailProvider(VerificationEmailProvider):
    async def send_code(self, target_email: str, code: str) -> DeliveryResult:
        if settings.is_production:
            return DeliveryResult(
                delivered=False,
                provider="mock",
                message="Mock delivery is disabled in production",
            )
        return DeliveryResult(
            delivered=True,
            provider="mock",
            message="Код отправлен в dev fallback.",
            dev_code=code,
        )

    async def send_reset_link(self, target_email: str, reset_link: str) -> DeliveryResult:
        import logging
        logging.getLogger("autorewier.auth").info(
            "password_reset_link_mock",
            extra={"email": target_email, "link": reset_link},
        )
        if settings.is_production:
            return DeliveryResult(
                delivered=False,
                provider="mock",
                message="Mock delivery is disabled in production",
            )
        return DeliveryResult(
            delivered=True,
            provider="mock",
            message=f"Ссылка сброса (dev): {reset_link}",
        )


def get_verification_email_provider() -> VerificationEmailProvider:
    if settings.smtp_host.strip() and settings.smtp_sender_email.strip():
        return SmtpVerificationEmailProvider()
    return MockVerificationEmailProvider()
