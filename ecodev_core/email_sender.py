"""
Module implementing generic email send
"""
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from smtplib import SMTP
from ssl import create_default_context

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.settings import SETTINGS


class EmailAuth(BaseSettings):
    """
    Simple authentication configuration class
    """
    email_smtp: str = ''
    email_sender: str = ''
    email_password: str = ''
    email_port: int = 587
    model_config = SettingsConfigDict(env_file='.env')


EMAIL_AUTH, EMAIL_SETTINGS = EmailAuth(), SETTINGS.smtp  # type: ignore[attr-defined]
_SENDER = EMAIL_SETTINGS.email_sender or EMAIL_AUTH.email_sender
_SMTP = EMAIL_SETTINGS.email_smtp or EMAIL_AUTH.email_smtp
_PASSWD = EMAIL_SETTINGS.email_password or EMAIL_AUTH.email_password
_PORT = EMAIL_SETTINGS.email_port or EMAIL_AUTH.email_port


def send_email(email: str, body: str, topic: str, images: dict[str, Path] | None = None) -> None:
    """
    Generic email sender.

    Attributes are:
        - email: The email to which to send
        - body: the email body
        - topic: the email topic
        - images: if any, the Dict of image tags:image paths to incorporate in the email
    """
    em = MIMEMultipart('related')
    em['From'] = _SENDER
    em['To'] = email
    em['Subject'] = topic
    em.attach(MIMEText(body, 'html'))
    for tag, img_path in (images or {}).items():
        with open(img_path, 'rb') as fp:
            img = MIMEImage(fp.read())
        img.add_header('Content-ID', f'<{tag}>')
        em.attach(img)

    with SMTP(_SMTP, _PORT) as server:
        server.ehlo()
        server.starttls(context=create_default_context())
        server.login(_SENDER, _PASSWD)
        server.sendmail(_SENDER, email, em.as_string())
