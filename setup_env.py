#!/usr/bin/env python3
"""
HealthNavi AI CDSS - Environment Setup Script

This script helps you create a .env file with the necessary configuration
for the HealthNavi AI CDSS application, including email settings.
"""

import os
import secrets
import string

def generate_secret_key(length=64):
    """Generate a secure random secret key."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_env_file():
    """Create .env file with configuration."""
    
    print("🏥 HealthNavi AI CDSS - Environment Setup")
    print("=" * 50)
    
    # Check if .env already exists
    if os.path.exists('.env'):
        response = input("⚠️  .env file already exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("❌ Setup cancelled.")
            return
    
    print("\n📧 Email Configuration Setup")
    print("Choose your email provider:")
    print("1. Gmail")
    print("2. Outlook/Hotmail")
    print("3. Yahoo")
    print("4. Custom SMTP")
    print("5. Skip email setup (for testing)")
    
    email_choice = input("\nEnter your choice (1-5): ").strip()
    
    # Default values
    smtp_server = "smtp.gmail.com"
    smtp_port = "587"
    smtp_username = ""
    smtp_password = ""
    smtp_use_tls = "true"
    smtp_use_ssl = "false"
    
    if email_choice == "1":  # Gmail
        print("\n📧 Gmail Configuration:")
        print("1. Enable 2-Factor Authentication on your Google account")
        print("2. Generate an App Password: https://myaccount.google.com/apppasswords")
        print("3. Use the App Password (not your regular password)")
        
        smtp_username = input("Enter your Gmail address: ").strip()
        smtp_password = input("Enter your Gmail App Password: ").strip()
        
    elif email_choice == "2":  # Outlook
        print("\n📧 Outlook/Hotmail Configuration:")
        smtp_server = "smtp-mail.outlook.com"
        smtp_username = input("Enter your Outlook email: ").strip()
        smtp_password = input("Enter your Outlook password: ").strip()
        
    elif email_choice == "3":  # Yahoo
        print("\n📧 Yahoo Configuration:")
        print("1. Enable 2-Factor Authentication")
        print("2. Generate an App Password")
        smtp_server = "smtp.mail.yahoo.com"
        smtp_username = input("Enter your Yahoo email: ").strip()
        smtp_password = input("Enter your Yahoo App Password: ").strip()
        
    elif email_choice == "4":  # Custom SMTP
        print("\n📧 Custom SMTP Configuration:")
        smtp_server = input("Enter SMTP server (e.g., smtp.example.com): ").strip()
        smtp_port = input("Enter SMTP port (default: 587): ").strip() or "587"
        smtp_username = input("Enter SMTP username: ").strip()
        smtp_password = input("Enter SMTP password: ").strip()
        
        tls_choice = input("Use TLS? (Y/n): ").strip().lower()
        smtp_use_tls = "true" if tls_choice != "n" else "false"
        
        ssl_choice = input("Use SSL? (y/N): ").strip().lower()
        smtp_use_ssl = "true" if ssl_choice == "y" else "false"
        
    elif email_choice == "5":  # Skip
        print("\n⏭️  Skipping email setup. You can configure it later in .env file.")
        
    else:
        print("❌ Invalid choice. Skipping email setup.")
    
    # Generate secure keys
    secret_key = generate_secret_key(64)
    encryption_key = generate_secret_key(32)
    
    # Create .env content
    env_content = f"""# HealthNavi AI CDSS - Environment Configuration
# This file contains environment variables for the application

# Application Settings
ENV=development
LOG_LEVEL=INFO

# Security Keys (Generated automatically)
SECRET_KEY={secret_key}
ENCRYPTION_KEY={encryption_key}

# Database Configuration
DB_USER=healthnavi_user
DB_PASSWORD=SecurePass123!
DB_HOST=db
DB_PORT=5432
DB_NAME=healthnavi_cdss
DATABASE_URL=postgresql://healthnavi_user:SecurePass123!@db:5432/healthnavi_cdss

# Email Configuration
SMTP_SERVER={smtp_server}
SMTP_PORT={smtp_port}
SMTP_USERNAME={smtp_username}
SMTP_PASSWORD={smtp_password}
SMTP_USE_TLS={smtp_use_tls}
SMTP_USE_SSL={smtp_use_ssl}
FROM_EMAIL=noreply@healthnavi.ai
FROM_NAME=HealthNavi AI CDSS

# Application URLs
BASE_URL=http://localhost:8050

# Instructions:
# 1. Make sure to set your email credentials above
# 2. For Gmail: Use App Password, not regular password
# 3. For production: Use dedicated email service (SendGrid, Mailgun, etc.)
# 4. Test email functionality by registering a user
"""
    
    # Write .env file
    try:
        with open('.env', 'w') as f:
            f.write(env_content)
        
        print("\n✅ .env file created successfully!")
        print("\n📋 Next steps:")
        print("1. Review the .env file and update email credentials if needed")
        print("2. Run: docker-compose up -d")
        print("3. Test email functionality by registering a user")
        print("4. Check health endpoint: http://localhost:8050/health")
        
        if email_choice in ["1", "2", "3", "4"]:
            print("\n📧 Email Configuration Summary:")
            print(f"   Server: {smtp_server}")
            print(f"   Port: {smtp_port}")
            print(f"   Username: {smtp_username}")
            print(f"   TLS: {smtp_use_tls}")
            print(f"   SSL: {smtp_use_ssl}")
        
    except Exception as e:
        print(f"❌ Error creating .env file: {e}")

if __name__ == "__main__":
    create_env_file()
