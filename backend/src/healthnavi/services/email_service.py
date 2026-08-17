"""
Email service for Empirico.
Handles email verification and notifications.
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import os
import secrets
import string

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails."""
    
    def __init__(self):
        """Initialize email service."""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = os.getenv("SMTP_USERNAME", "")
        self.sender_password = os.getenv("SMTP_PASSWORD", "")
        self.app_name = os.getenv("APP_NAME", "Empirico")
        self.base_url = os.getenv("BASE_URL", "http://localhost:8050")
        # Optional deep link so mobile can open the reset flow in-app (must match Android/iOS URL handler)
        self.password_reset_deep_link = os.getenv(
            "PASSWORD_RESET_DEEP_LINK_TEMPLATE",
            "empirico://password-reset?token={token}",
        )
        
        # Check if email is configured
        if not self.sender_email or not self.sender_password:
            logger.warning("Email service not configured - SMTP credentials missing")
            logger.warning(f"SMTP_USERNAME: {'SET' if self.sender_email else 'NOT SET'}")
            logger.warning(f"SMTP_PASSWORD: {'SET' if self.sender_password else 'NOT SET'}")
            self.is_configured = False
        else:
            self.is_configured = True
            logger.info(f"Email service configured with {self.sender_email}")
    
    def generate_verification_token(self, length: int = 32) -> str:
        """Generate a secure verification token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def send_verification_email(self, email: str, username: str, verification_token: str) -> bool:
        """Send email verification email."""
        if not self.is_configured:
            logger.warning("Email service not configured - cannot send verification email")
            return False
        
        try:
            # Create verification URL
            verification_url = f"{self.base_url}/api/v2/auth/verify-email?token={verification_token}"
            
            # Create email content
            subject = f"Verify Your Email - {self.app_name}"
            
            html_content = f"""
            <html>
            <body>
                <h2>Welcome to {self.app_name}!</h2>
                <p>Hello {username},</p>
                <p>Thank you for registering with {self.app_name}. Please verify your email address by clicking the link below:</p>
                <p><a href="{verification_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email Address</a></p>
                <p>Or copy and paste this link into your browser:</p>
                <p>{verification_url}</p>
                <p>This link will expire in 24 hours.</p>
                <p>If you didn't create an account with {self.app_name}, please ignore this email.</p>
                <br>
                <p>Best regards,<br>The {self.app_name} Team</p>
            </body>
            </html>
            """
            
            text_content = f"""
            Welcome to {self.app_name}!
            
            Hello {username},
            
            Thank you for registering with {self.app_name}. Please verify your email address by visiting the link below:
            
            {verification_url}
            
            This link will expire in 24 hours.
            
            If you didn't create an account with {self.app_name}, please ignore this email.
            
            Best regards,
            The {self.app_name} Team
            """
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = email
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, email, message.as_string())
            
            logger.info(f"Verification email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {str(e)}")
            return False
    
    def send_password_reset_email(self, email: str, username: str, reset_token: str) -> bool:
        """Send password reset email."""
        if not self.is_configured:
            logger.warning("Email service not configured - cannot send password reset email")
            return False
        
        try:
            # Web reset URL — frontend extracts token and shows reset modal (BASE_URL e.g. https://empirico.ai)
            reset_url = f"{self.base_url}?token={reset_token}"
            deep_link = self.password_reset_deep_link.format(token=reset_token)
            
            # Create email content
            subject = f"Password Reset - {self.app_name}"
            
            html_content = f"""
            <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>Hello {username},</p>
                <p>You requested a password reset for your {self.app_name} account. Use one of the options below:</p>
                <p><a href="{deep_link}" style="background-color: #00695c; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-bottom: 8px;">Open in Empirico app</a></p>
                <p><a href="{reset_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset password in browser</a></p>
                <p>Or copy one of these links:</p>
                <p><strong>App:</strong> {deep_link}</p>
                <p><strong>Browser:</strong> {reset_url}</p>
                <p>On many phones you can tap the app link and choose <strong>Open with</strong> Empirico or the browser.</p>
                <p>This link will expire in 1 hour.</p>
                <p>If you didn't request a password reset, please ignore this email.</p>
                <br>
                <p>Best regards,<br>The {self.app_name} Team</p>
            </body>
            </html>
            """
            
            text_content = f"""
            Password Reset Request
            
            Hello {username},
            
            You requested a password reset for your {self.app_name} account. Choose one:
            
            Open in the Empirico app (copy into your browser or tap; use "Open with" if asked):
            {deep_link}
            
            Or reset in your web browser:
            {reset_url}
            
            This link will expire in 1 hour.
            
            If you didn't request a password reset, please ignore this email.
            
            Best regards,
            The {self.app_name} Team
            """
            
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = email
            
            # Add text and HTML parts
            text_part = MIMEText(text_content, "plain")
            html_part = MIMEText(html_content, "html")
            
            message.attach(text_part)
            message.attach(html_part)
            
            # Send email
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=context)
                server.login(self.sender_email, self.sender_password)
                server.sendmail(self.sender_email, email, message.as_string())
            
            logger.info(f"Password reset email sent to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {str(e)}")
            return False


# Initialize email service
email_service = EmailService()
