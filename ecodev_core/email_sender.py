"""
Module implementing generic email send
"""
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from smtplib import SMTP
from ssl import create_default_context

from ecodev_core.settings import SETTINGS


def send_email(email: str, body: str, topic: str, images: dict[str, Path] | None = None) -> None:
    """
    Generic email sender.

    Attributes are:
        - email: The email to which to send
        - body: the email body
        - topic: the email topic
        - images: if any, the Dict of image tags:image paths to incorporate in the email
    """

    SETTINGS.smtp.email_port
    em = MIMEMultipart('related')
    em['From'] = SETTINGS.smtp.email_sender
    em['To'] = email
    em['Subject'] = topic
    em.attach(MIMEText(body, 'html'))
    for tag, img_path in (images or {}).items():
        with open(img_path, 'rb') as fp:
            img = MIMEImage(fp.read())
        img.add_header('Content-ID', f'<{tag}>')
        em.attach(img)

    with SMTP(SETTINGS.smtp.email_smtp, SETTINGS.smtp.email_port) as server:
        server.ehlo()
        server.starttls(context=create_default_context())
        server.login(SETTINGS.smtp.email_sender, SETTINGS.smtp.email_password)
        server.sendmail(SETTINGS.smtp.email_sender, email, em.as_string())
