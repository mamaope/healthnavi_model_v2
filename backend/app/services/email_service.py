"""
Email Service for HealthNavi AI CDSS

This service handles all email operations including verification emails,
notifications, and system communications.
"""

import logging
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
import os
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class EmailService:
    """Service class for email operations."""
    
    def __init__(self):
        """Initialize email service with configuration."""
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@healthnavi.ai")
        self.from_name = os.getenv("FROM_NAME", "HealthNavi AI CDSS")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
        
        # Email templates
        self.templates = {
            "verification": self._get_verification_template(),
            "welcome": self._get_welcome_template(),
            "password_reset": self._get_password_reset_template()
        }
        
        # Thread pool for async email sending
        self.executor = ThreadPoolExecutor(max_workers=3)
    
    def _get_verification_template(self) -> str:
        """Get email verification template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Verification - HealthNavi AI CDSS</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }}
        .container {{
            background-color: #ffffff;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
        }}
        .logo {{
            font-size: 28px;
            font-weight: bold;
            color: #2c5aa0;
            margin-bottom: 10px;
        }}
        .subtitle {{
            color: #666;
            font-size: 16px;
        }}
        .content {{
            margin-bottom: 30px;
        }}
        .verification-box {{
            background-color: #f8f9fa;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
        }}
        .verification-link {{
            display: inline-block;
            background-color: #2c5aa0;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .verification-link:hover {{
            background-color: #1e3d6f;
        }}
        .token-display {{
            background-color: #e9ecef;
            padding: 10px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 14px;
            word-break: break-all;
            margin: 10px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e9ecef;
            color: #666;
            font-size: 14px;
        }}
        .security-note {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            color: #856404;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🏥 HealthNavi AI CDSS</div>
            <div class="subtitle">Clinical Decision Support System</div>
        </div>
        
        <div class="content">
            <h2>Welcome to HealthNavi AI CDSS!</h2>
            
            <p>Thank you for registering with HealthNavi AI CDSS. To complete your account setup and ensure the security of your medical information, please verify your email address.</p>
            
            <div class="verification-box">
                <h3>📧 Email Verification Required</h3>
                <p>Click the button below to verify your email address:</p>
                
                <a href="{verification_url}" class="verification-link">
                    ✅ Verify Email Address
                </a>
                
                <p style="margin-top: 15px; font-size: 14px; color: #666;">
                    Or copy and paste this link into your browser:<br>
                    <span style="word-break: break-all; color: #2c5aa0;">{verification_url}</span>
                </p>
            </div>
            
            <div class="security-note">
                <strong>🔒 Security Information:</strong><br>
                • This verification link expires in 24 hours<br>
                • The link can only be used once<br>
                • If you didn't create this account, please ignore this email<br>
                • Your account will remain inactive until email verification is complete
            </div>
            
            <h3>What happens next?</h3>
            <ul>
                <li>✅ Click the verification link above</li>
                <li>✅ Your account will be activated automatically</li>
                <li>✅ You can then log in and access the system</li>
                <li>✅ Start using HealthNavi AI CDSS for clinical decision support</li>
            </ul>
            
            <p><strong>Need help?</strong> If you're having trouble with the verification link, you can request a new one by logging in to your account or contacting our support team.</p>
        </div>
        
        <div class="footer">
            <p>This email was sent by HealthNavi AI CDSS</p>
            <p>© 2025 HealthNavi AI. All rights reserved.</p>
            <p style="font-size: 12px; color: #999;">
                This is an automated message. Please do not reply to this email.
            </p>
        </div>
    </div>
</body>
</html>
        """
    
    def _get_welcome_template(self) -> str:
        """Get welcome email template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Welcome to HealthNavi AI CDSS</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            background-color: #2c5aa0;
            color: white;
            padding: 20px;
            border-radius: 5px;
        }}
        .content {{
            padding: 20px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🏥 Welcome to HealthNavi AI CDSS!</h1>
    </div>
    <div class="content">
        <h2>Hello {first_name}!</h2>
        <p>Your email has been successfully verified and your account is now active.</p>
        <p>You can now access all features of the HealthNavi AI Clinical Decision Support System.</p>
        <p>Thank you for choosing HealthNavi AI CDSS for your clinical decision support needs.</p>
    </div>
</body>
</html>
        """
    
    def _get_password_reset_template(self) -> str:
        """Get password reset template."""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Password Reset - HealthNavi AI CDSS</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            background-color: #dc3545;
            color: white;
            padding: 20px;
            border-radius: 5px;
        }}
        .content {{
            padding: 20px;
        }}
        .reset-link {{
            background-color: #dc3545;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔒 Password Reset Request</h1>
    </div>
    <div class="content">
        <h2>Hello {first_name}!</h2>
        <p>You have requested to reset your password for your HealthNavi AI CDSS account.</p>
        <p>Click the link below to reset your password:</p>
        <a href="{reset_url}" class="reset-link">Reset Password</a>
        <p>This link will expire in 1 hour for security reasons.</p>
        <p>If you didn't request this password reset, please ignore this email.</p>
    </div>
</body>
</html>
        """
    
    def _create_smtp_connection(self) -> smtplib.SMTP:
        """Create SMTP connection."""
        try:
            if self.use_ssl:
                # Use SSL
                context = ssl.create_default_context()
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, context=context)
            else:
                # Use TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                if self.use_tls:
                    server.starttls()
            
            # Login if credentials are provided
            if self.smtp_username and self.smtp_password:
                server.login(self.smtp_username, self.smtp_password)
            
            return server
        except Exception as e:
            logger.error(f"Failed to create SMTP connection: {e}")
            raise
    
    def _send_email_sync(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email synchronously."""
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text content if provided
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            # Add HTML content
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            server = self._create_smtp_connection()
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email asynchronously."""
        try:
            # Run email sending in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._send_email_sync,
                to_email,
                subject,
                html_content,
                text_content
            )
            return result
        except Exception as e:
            logger.error(f"Async email sending failed for {to_email}: {e}")
            return False
    
    async def send_verification_email(self, to_email: str, first_name: str, verification_token: str, base_url: str = None) -> bool:
        """Send email verification email."""
        try:
            # Generate verification URL
            if not base_url:
                base_url = os.getenv("BASE_URL", "http://localhost:8050")
            
            verification_url = f"{base_url}/auth/verify-email?token={verification_token}"
            
            # Prepare email content
            subject = "🏥 Verify Your Email - HealthNavi AI CDSS"
            html_content = self.templates["verification"].format(
                verification_url=verification_url,
                first_name=first_name,
                verification_token=verification_token
            )
            
            # Plain text version
            text_content = f"""
HealthNavi AI CDSS - Email Verification

Hello {first_name},

Thank you for registering with HealthNavi AI CDSS. To complete your account setup, please verify your email address.

Click this link to verify your email:
{verification_url}

This verification link expires in 24 hours and can only be used once.

If you didn't create this account, please ignore this email.

Best regards,
HealthNavi AI CDSS Team
            """
            
            # Send email
            success = await self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Verification email sent to {to_email}")
            else:
                logger.error(f"Failed to send verification email to {to_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending verification email to {to_email}: {e}")
            return False
    
    async def send_welcome_email(self, to_email: str, first_name: str) -> bool:
        """Send welcome email after verification."""
        try:
            subject = "🎉 Welcome to HealthNavi AI CDSS!"
            html_content = self.templates["welcome"].format(first_name=first_name)
            
            text_content = f"""
Welcome to HealthNavi AI CDSS!

Hello {first_name},

Your email has been successfully verified and your account is now active.

You can now access all features of the HealthNavi AI Clinical Decision Support System.

Thank you for choosing HealthNavi AI CDSS!

Best regards,
HealthNavi AI CDSS Team
            """
            
            success = await self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Welcome email sent to {to_email}")
            else:
                logger.error(f"Failed to send welcome email to {to_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending welcome email to {to_email}: {e}")
            return False
    
    async def send_password_reset_email(self, to_email: str, first_name: str, reset_token: str, base_url: str = None) -> bool:
        """Send password reset email."""
        try:
            if not base_url:
                base_url = os.getenv("BASE_URL", "http://localhost:8050")
            
            reset_url = f"{base_url}/auth/reset-password?token={reset_token}"
            
            subject = "🔒 Password Reset - HealthNavi AI CDSS"
            html_content = self.templates["password_reset"].format(
                first_name=first_name,
                reset_url=reset_url
            )
            
            text_content = f"""
Password Reset Request - HealthNavi AI CDSS

Hello {first_name},

You have requested to reset your password for your HealthNavi AI CDSS account.

Click this link to reset your password:
{reset_url}

This link will expire in 1 hour for security reasons.

If you didn't request this password reset, please ignore this email.

Best regards,
HealthNavi AI CDSS Team
            """
            
            success = await self.send_email(to_email, subject, html_content, text_content)
            
            if success:
                logger.info(f"Password reset email sent to {to_email}")
            else:
                logger.error(f"Failed to send password reset email to {to_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending password reset email to {to_email}: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test email service connection."""
        try:
            server = self._create_smtp_connection()
            server.quit()
            logger.info("Email service connection test successful")
            return True
        except Exception as e:
            logger.error(f"Email service connection test failed: {e}")
            return False
    
    def get_configuration_status(self) -> Dict[str, Any]:
        """Get email service configuration status."""
        return {
            "smtp_server": self.smtp_server,
            "smtp_port": self.smtp_port,
            "from_email": self.from_email,
            "from_name": self.from_name,
            "use_tls": self.use_tls,
            "use_ssl": self.use_ssl,
            "has_credentials": bool(self.smtp_username and self.smtp_password),
            "connection_test": self.test_connection()
        }

# Global email service instance
email_service = EmailService()
