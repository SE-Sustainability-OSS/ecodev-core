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


class EmailAuth(BaseSettings):
    """
    Simple authentication configuration class
    """
    email_smtp: str = ''
    email_sender: str = ''
    email_password: str = ''
    model_config = SettingsConfigDict(env_file='.env')


EMAIL_AUTH = EmailAuth()


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
    em['From'] = EMAIL_AUTH.email_sender
    em['To'] = email
    em['Subject'] = topic
    em.attach(MIMEText(body, 'html'))
    for tag, img_path in (images or {}).items():
        with open(img_path, 'rb') as fp:
            img = MIMEImage(fp.read())
        img.add_header('Content-ID', f'<{tag}>')
        em.attach(img)

    with SMTP(EMAIL_AUTH.email_smtp, 587) as server:
        server.ehlo()
        server.starttls(context=create_default_context())
        server.login(EMAIL_AUTH.email_sender, EMAIL_AUTH.email_password)
        server.sendmail(EMAIL_AUTH.email_sender, email, em.as_string())
