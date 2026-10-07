"""Replaceable mail transport. No environment loading or live transport auto-selection."""
from dataclasses import dataclass, field
from email.message import EmailMessage
import re
import smtplib
import ssl
from typing import Protocol


class MailDeliveryError(Exception):
    pass


def address(value):
    if not isinstance(value,str) or len(value)>254 or not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+",value):
        raise MailDeliveryError("Invalid mail address")
    if not value.isascii(): raise MailDeliveryError("Invalid mail address")
    return value


@dataclass(frozen=True)
class TextMail:
    recipient: str = field(repr=False)
    subject: str
    body: str = field(repr=False)


class MailTransport(Protocol):
    def send(self, message: TextMail) -> None: ...


class DisabledMailTransport:
    def send(self, message): raise MailDeliveryError("Mail delivery is not configured")


class MemoryMailTransport:
    """For isolated tests only. Never chosen automatically for a running application."""
    def __init__(self): self.messages=[]
    def send(self,message): self.messages.append(message)


@dataclass(frozen=True)
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str = field(repr=False)
    sender: str = "no-reply@hakase-uranai.jp"
    security: str = "starttls"
    timeout: float = 10


class SMTPMailTransport:
    def __init__(self, config: SMTPConfig, smtp_factory=None):
        if config.security not in ("starttls","ssl") or not isinstance(config.port,int) or not 1<=config.port<=65535:
            raise MailDeliveryError("Invalid SMTP configuration")
        if not config.host or any(c.isspace() for c in config.host) or not config.username or not config.password or not 0<config.timeout<=60:
            raise MailDeliveryError("Invalid SMTP configuration")
        address(config.sender)
        self.config=config
        self.factory=smtp_factory

    def send(self, message: TextMail):
        address(message.recipient)
        if not isinstance(message.subject,str) or any(c in message.subject for c in "\r\n") or not isinstance(message.body,str):
            raise MailDeliveryError("Invalid mail message")
        config=self.config
        mail=EmailMessage()
        mail["From"]=config.sender; mail["To"]=message.recipient; mail["Subject"]=message.subject
        mail.set_content(message.body)
        context=ssl.create_default_context()
        factory=self.factory or (smtplib.SMTP_SSL if config.security=="ssl" else smtplib.SMTP)
        try:
            options={"timeout":config.timeout}
            if config.security=="ssl": options["context"]=context
            with factory(config.host,config.port,**options) as connection:
                connection.ehlo()
                if config.security=="starttls":
                    connection.starttls(context=context); connection.ehlo()
                connection.login(config.username,config.password)
                refused=connection.send_message(mail)
                if refused: raise MailDeliveryError("Mail delivery failed")
        except Exception:
            # The SMTP server's text may contain credentials or recipients. Never propagate it.
            raise MailDeliveryError("Mail delivery failed") from None
