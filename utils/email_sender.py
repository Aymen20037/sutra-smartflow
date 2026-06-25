import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from dotenv import load_dotenv

load_dotenv()


def send_verification_code(to_email: str, code: str) -> bool:
    """
    Envoie un code de vérification à 6 chiffres par email via Gmail SMTP.
    Retourne True si l'envoi a réussi, False sinon.
    """
    smtp_email = os.getenv("SMTP_EMAIL")
    smtp_password = os.getenv("SMTP_APP_PASSWORD")
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    sender_name = os.getenv("SMTP_SENDER_NAME", "Système de Transit Douanier")

    if not smtp_email or not smtp_password:
        print("SMTP_EMAIL ou SMTP_APP_PASSWORD manquant dans .env")
        return False

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: auto;
                border: 1px solid #eee; border-radius: 10px; padding: 24px;">
        <h2 style="color: #111;">Réinitialisation du mot de passe</h2>
        <p>Bonjour,</p>
        <p>
            Vous avez demandé la réinitialisation de votre mot de passe pour
            l'application <strong>Transit Douanier (Sutra)</strong>.
        </p>
        <p>Votre code de vérification est :</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 6px;
                    text-align: center; background: #f5f5f5; border-radius: 8px;
                    padding: 14px; margin: 20px 0;">
            {code}
        </div>
        <p>Ce code est valable <strong>10 minutes</strong>.</p>
        <p style="color: #888; font-size: 13px;">
            Si vous n'êtes pas à l'origine de cette demande, ignorez cet email
            et votre mot de passe ne sera pas modifié.
        </p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
        <p style="color: #aaa; font-size: 12px;">Système de Transit Douanier</p>
    </div>
    """

    text_content = f"""
Bonjour,

Vous avez demandé la réinitialisation de votre mot de passe pour l'application
Transit Douanier (Sutra).

Votre code de vérification est : {code}

Ce code est valable 10 minutes.

Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.
"""

    message = MIMEMultipart("alternative")
    message["From"] = f"{sender_name} <{smtp_email}>"
    message["To"] = to_email
    message["Subject"] = "Code de vérification - Réinitialisation du mot de passe"
    message.attach(MIMEText(text_content, "plain", "utf-8"))
    message.attach(MIMEText(html_content, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.send_message(message)
        return True
    except Exception as e:
        print(f"Erreur envoi email (SMTP Gmail) : {e}")
        return False
