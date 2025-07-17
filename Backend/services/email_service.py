#!/usr/bin/env python3
"""
Professional Email Service using ZeptoMail API
Handles OTP verification emails with Dubai-themed HTML templates
"""

import requests
import json
import logging
import os
from typing import Dict, Optional, Any
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)


class ZeptoMailService:
    """Professional email service using ZeptoMail API"""
    
    def __init__(self):
        self.api_url = "https://api.zeptomail.com/v1.1/email"
        self.api_key = os.getenv("ZEPTOMAIL_API_KEY")
        if not self.api_key:
            raise ValueError("ZEPTOMAIL_API_KEY environment variable is required")
        self.sender_email = "noreply@mydscvr.ai"
        self.sender_name = "MyDSCVR Dubai Events"
        
        self.headers = {
            'accept': "application/json",
            'content-type': "application/json",
            'authorization': f"Zoho-enczapikey {self.api_key}",
        }
    
    def create_otp_html_template(self, otp_code: str, user_name: str = "User", expires_in_minutes: int = 10) -> str:
        """
        Create professional HTML template for OTP verification with Dubai branding
        """
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyDSCVR - Email Verification</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Comfortaa:wght@400;600;700&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', Arial, sans-serif;
            line-height: 1.6;
            color: #2C3E50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 50%, #45B7D1 100%);
            padding: 40px 30px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }}
        
        .header::before {{
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="dots" width="10" height="10" patternUnits="userSpaceOnUse"><circle cx="5" cy="5" r="1.5" fill="rgba(255,255,255,0.1)"/></pattern></defs><rect width="100" height="100" fill="url(%23dots)"/></svg>');
            animation: float 20s ease-in-out infinite;
        }}
        
        @keyframes float {{
            0%, 100% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-20px); }}
        }}
        
        .logo {{
            width: 60px;
            height: 60px;
            background: #ffffff;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Comfortaa', sans-serif;
            font-weight: 700;
            font-size: 24px;
            color: #FF6B6B;
            position: relative;
            z-index: 1;
            box-shadow: 0 8px 25px rgba(255,255,255,0.2);
        }}
        
        .brand-name {{
            font-family: 'Comfortaa', sans-serif;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
            position: relative;
            z-index: 1;
        }}
        
        .brand-tagline {{
            color: rgba(255,255,255,0.9);
            font-size: 16px;
            font-weight: 500;
            position: relative;
            z-index: 1;
        }}
        
        .content {{
            padding: 50px 40px;
            background: #ffffff;
        }}
        
        .greeting {{
            font-size: 24px;
            font-weight: 600;
            color: #2C3E50;
            margin-bottom: 20px;
        }}
        
        .message {{
            font-size: 16px;
            color: #5D6D7E;
            margin-bottom: 40px;
            line-height: 1.7;
        }}
        
        .otp-container {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            margin: 40px 0;
            position: relative;
            overflow: hidden;
        }}
        
        .otp-container::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><radialGradient id="grad"><stop offset="0%" stop-color="rgba(255,255,255,0.1)"/><stop offset="100%" stop-color="rgba(255,255,255,0)"/></radialGradient></defs><circle cx="20" cy="20" r="15" fill="url(%23grad)"/><circle cx="80" cy="80" r="20" fill="url(%23grad)"/></svg>');
            pointer-events: none;
        }}
        
        .otp-label {{
            color: rgba(255,255,255,0.9);
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
            position: relative;
            z-index: 1;
        }}
        
        .otp-code {{
            font-family: 'Inter', monospace;
            font-size: 36px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 8px;
            margin: 15px 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
            z-index: 1;
        }}
        
        .otp-expires {{
            color: rgba(255,255,255,0.8);
            font-size: 14px;
            font-weight: 500;
            position: relative;
            z-index: 1;
        }}
        
        .security-notice {{
            background: #F8F9FA;
            border-left: 4px solid #4ECDC4;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }}
        
        .security-title {{
            font-weight: 600;
            color: #2C3E50;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        
        .security-text {{
            color: #5D6D7E;
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .footer {{
            background: #F8F9FA;
            padding: 30px 40px;
            text-align: center;
            border-top: 1px solid #E5E8EC;
        }}
        
        .footer-text {{
            color: #95A5A6;
            font-size: 14px;
            margin-bottom: 15px;
        }}
        
        .social-links {{
            margin: 20px 0;
        }}
        
        .social-link {{
            display: inline-block;
            margin: 0 10px;
            padding: 8px 12px;
            background: #ffffff;
            border-radius: 8px;
            text-decoration: none;
            color: #667eea;
            font-weight: 500;
            font-size: 14px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .contact-info {{
            color: #95A5A6;
            font-size: 12px;
            margin-top: 20px;
        }}
        
        .dubai-pattern {{
            background-image: 
                radial-gradient(circle at 25% 25%, rgba(255, 107, 107, 0.1) 0%, transparent 50%),
                radial-gradient(circle at 75% 75%, rgba(78, 205, 196, 0.1) 0%, transparent 50%);
        }}
        
        @media only screen and (max-width: 600px) {{
            .email-container {{
                margin: 10px;
                border-radius: 15px;
            }}
            
            .header {{
                padding: 30px 20px;
            }}
            
            .content {{
                padding: 30px 25px;
            }}
            
            .otp-code {{
                font-size: 28px;
                letter-spacing: 4px;
            }}
            
            .footer {{
                padding: 25px 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <!-- Header with Dubai-themed branding -->
        <div class="header dubai-pattern">
            <div class="logo">M</div>
            <div class="brand-name">MyDSCVR</div>
            <div class="brand-tagline">Discover Dubai's Hidden Gems</div>
        </div>
        
        <!-- Main Content -->
        <div class="content">
            <div class="greeting">Hello {user_name}! 👋</div>
            
            <div class="message">
                Welcome to MyDSCVR! We're excited to have you join Dubai's premier events discovery platform. 
                To complete your account verification, please use the following One-Time Password (OTP):
            </div>
            
            <!-- OTP Display -->
            <div class="otp-container">
                <div class="otp-label">Your Verification Code</div>
                <div class="otp-code">{otp_code}</div>
                <div class="otp-expires">⏰ Expires in {expires_in_minutes} minutes</div>
            </div>
            
            <!-- Security Notice -->
            <div class="security-notice">
                <div class="security-title">🔒 Security Notice</div>
                <div class="security-text">
                    • This code is valid for {expires_in_minutes} minutes only<br>
                    • Never share this code with anyone<br>
                    • MyDSCVR will never ask for your OTP via phone or social media<br>
                    • If you didn't request this verification, please ignore this email
                </div>
            </div>
            
            <div class="message">
                Once verified, you'll be able to:
                <br><br>
                ✨ <strong>Discover hidden gems</strong> across Dubai<br>
                🎯 <strong>Get personalized recommendations</strong> for your family<br>
                💎 <strong>Access exclusive events</strong> before they're public<br>
                📅 <strong>Save and organize</strong> your favorite events<br>
                🏆 <strong>Build discovery streaks</strong> and unlock achievements
            </div>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <div class="footer-text">
                Thank you for choosing MyDSCVR - Your gateway to Dubai's best experiences!
            </div>
            
            <div class="social-links">
                <a href="https://mydscvr.ai" class="social-link">🌐 Visit Website</a>
                <a href="mailto:support@mydscvr.ai" class="social-link">✉️ Contact Support</a>
            </div>
            
            <div class="contact-info">
                MyDSCVR Dubai Events Platform<br>
                📧 support@mydscvr.ai | 🌐 mydscvr.ai<br>
                Discover • Experience • Remember
            </div>
        </div>
    </div>
</body>
</html>
        """
    
    def create_welcome_html_template(self, user_name: str) -> str:
        """
        Create welcome email template after successful verification
        """
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to MyDSCVR!</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Comfortaa:wght@400;600;700&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', Arial, sans-serif;
            line-height: 1.6;
            color: #2C3E50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 50%, #45B7D1 100%);
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }}
        
        .logo {{
            width: 60px;
            height: 60px;
            background: #ffffff;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Comfortaa', sans-serif;
            font-weight: 700;
            font-size: 24px;
            color: #FF6B6B;
            box-shadow: 0 8px 25px rgba(255,255,255,0.2);
        }}
        
        .brand-name {{
            font-family: 'Comfortaa', sans-serif;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        
        .content {{
            padding: 50px 40px;
        }}
        
        .welcome-title {{
            font-size: 32px;
            font-weight: 700;
            color: #2C3E50;
            text-align: center;
            margin-bottom: 20px;
        }}
        
        .welcome-message {{
            font-size: 18px;
            color: #5D6D7E;
            text-align: center;
            margin-bottom: 40px;
        }}
        
        .features-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin: 40px 0;
        }}
        
        .feature-card {{
            background: #F8F9FA;
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }}
        
        .feature-icon {{
            font-size: 32px;
            margin-bottom: 15px;
        }}
        
        .feature-title {{
            font-weight: 600;
            color: #2C3E50;
            margin-bottom: 10px;
        }}
        
        .feature-text {{
            color: #5D6D7E;
            font-size: 14px;
        }}
        
        .cta-button {{
            display: inline-block;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #ffffff;
            padding: 15px 30px;
            border-radius: 12px;
            text-decoration: none;
            font-weight: 600;
            font-size: 16px;
            margin: 30px auto;
            text-align: center;
            transition: all 0.3s ease;
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.3);
        }}
        
        .footer {{
            background: #F8F9FA;
            padding: 30px;
            text-align: center;
        }}
        
        @media only screen and (max-width: 600px) {{
            .features-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="logo">M</div>
            <div class="brand-name">MyDSCVR</div>
        </div>
        
        <div class="content">
            <div class="welcome-title">🎉 Welcome to MyDSCVR, {user_name}!</div>
            <div class="welcome-message">
                Your account has been successfully verified! You're now part of Dubai's most exclusive events community.
            </div>
            
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">💎</div>
                    <div class="feature-title">Hidden Gems Daily</div>
                    <div class="feature-text">Discover exclusive events and experiences most Dubai residents never find</div>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🎯</div>
                    <div class="feature-title">Smart Recommendations</div>
                    <div class="feature-text">AI-powered suggestions based on your family's preferences and interests</div>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📅</div>
                    <div class="feature-title">Event Organization</div>
                    <div class="feature-text">Save, organize, and track your favorite events and experiences</div>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🏆</div>
                    <div class="feature-title">Discovery Streaks</div>
                    <div class="feature-text">Build streaks, unlock achievements, and become a Dubai discovery expert</div>
                </div>
            </div>
            
            <div style="text-align: center;">
                <a href="https://mydscvr.ai" class="cta-button">Start Discovering Dubai 🚀</a>
            </div>
        </div>
        
        <div class="footer">
            <div style="color: #95A5A6; font-size: 14px;">
                Ready to uncover Dubai's best-kept secrets? Your journey starts now!
            </div>
        </div>
    </div>
</body>
</html>
        """
    
    async def send_otp_email(
        self, 
        recipient_email: str, 
        recipient_name: str, 
        otp_code: str,
        expires_in_minutes: int = 10
    ) -> Dict[str, Any]:
        """
        Send OTP verification email
        """
        try:
            html_template = self.create_otp_html_template(
                otp_code=otp_code,
                user_name=recipient_name,
                expires_in_minutes=expires_in_minutes
            )
            
            payload = {
                "from": {
                    "address": self.sender_email,
                    "name": self.sender_name
                },
                "to": [{
                    "email_address": {
                        "address": recipient_email,
                        "name": recipient_name
                    }
                }],
                "subject": f"🔐 MyDSCVR Verification Code: {otp_code}",
                "htmlbody": html_template
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ OTP email sent successfully to {recipient_email}")
                return {
                    "success": True,
                    "message": "OTP email sent successfully",
                    "response": response.json()
                }
            else:
                logger.error(f"❌ Failed to send OTP email: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Email service error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception sending OTP email: {e}")
            return {
                "success": False,
                "error": "Email service exception",
                "details": str(e)
            }
    
    def create_password_reset_html_template(self, user_name: str, reset_code: str, expires_in_minutes: int = 15) -> str:
        """
        Create password reset email template
        """
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MyDSCVR - Password Reset</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Comfortaa:wght@400;600;700&display=swap');
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Inter', Arial, sans-serif;
            line-height: 1.6;
            color: #2C3E50;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
        }}
        
        .email-container {{
            max-width: 600px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        
        .header {{
            background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 50%, #45B7D1 100%);
            padding: 40px 30px;
            text-align: center;
            position: relative;
        }}
        
        .logo {{
            width: 60px;
            height: 60px;
            background: #ffffff;
            border-radius: 50%;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Comfortaa', sans-serif;
            font-weight: 700;
            font-size: 24px;
            color: #FF6B6B;
            box-shadow: 0 8px 25px rgba(255,255,255,0.2);
        }}
        
        .brand-name {{
            font-family: 'Comfortaa', sans-serif;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}
        
        .brand-tagline {{
            color: rgba(255,255,255,0.9);
            font-size: 16px;
            font-weight: 500;
        }}
        
        .content {{
            padding: 50px 40px;
        }}
        
        .title {{
            font-size: 24px;
            font-weight: 600;
            color: #2C3E50;
            margin-bottom: 20px;
            text-align: center;
        }}
        
        .message {{
            font-size: 16px;
            color: #5D6D7E;
            margin-bottom: 30px;
            line-height: 1.7;
        }}
        
        .reset-container {{
            background: linear-gradient(135deg, #FF6B6B 0%, #4ECDC4 100%);
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            margin: 30px 0;
        }}
        
        .reset-label {{
            color: rgba(255,255,255,0.9);
            font-size: 14px;
            font-weight: 500;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        
        .reset-code {{
            font-family: 'Inter', monospace;
            font-size: 32px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 6px;
            margin: 15px 0;
            text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        
        .reset-expires {{
            color: rgba(255,255,255,0.8);
            font-size: 14px;
            font-weight: 500;
        }}
        
        .security-notice {{
            background: #FFF3CD;
            border-left: 4px solid #FFC107;
            padding: 20px;
            margin: 30px 0;
            border-radius: 8px;
        }}
        
        .security-title {{
            font-weight: 600;
            color: #856404;
            margin-bottom: 10px;
            font-size: 16px;
        }}
        
        .security-text {{
            color: #856404;
            font-size: 14px;
            line-height: 1.6;
        }}
        
        .footer {{
            background: #F8F9FA;
            padding: 30px;
            text-align: center;
        }}
        
        .footer-text {{
            color: #95A5A6;
            font-size: 14px;
        }}
        
        @media only screen and (max-width: 600px) {{
            .content {{
                padding: 30px 25px;
            }}
            
            .reset-code {{
                font-size: 24px;
                letter-spacing: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="email-container">
        <div class="header">
            <div class="logo">M</div>
            <div class="brand-name">MyDSCVR</div>
            <div class="brand-tagline">Discover Dubai's Hidden Gems</div>
        </div>
        
        <div class="content">
            <div class="title">🔐 Password Reset Request</div>
            
            <div class="message">
                Hello {user_name},<br><br>
                We received a request to reset your MyDSCVR account password. If you made this request, 
                please use the following verification code to proceed:
            </div>
            
            <div class="reset-container">
                <div class="reset-label">Password Reset Code</div>
                <div class="reset-code">{reset_code}</div>
                <div class="reset-expires">⏰ Expires in {expires_in_minutes} minutes</div>
            </div>
            
            <div class="security-notice">
                <div class="security-title">⚠️ Security Notice</div>
                <div class="security-text">
                    • This code expires in {expires_in_minutes} minutes<br>
                    • Never share this code with anyone<br>
                    • If you didn't request this reset, please ignore this email<br>
                    • Your current password remains active until you complete the reset process
                </div>
            </div>
            
            <div class="message">
                If you didn't request a password reset, you can safely ignore this email. 
                Your account security remains intact.
            </div>
        </div>
        
        <div class="footer">
            <div class="footer-text">
                MyDSCVR Security Team<br>
                📧 support@mydscvr.ai | 🌐 mydscvr.ai
            </div>
        </div>
    </div>
</body>
</html>
        """

    async def send_welcome_email(
        self, 
        recipient_email: str, 
        recipient_name: str
    ) -> Dict[str, Any]:
        """
        Send welcome email after successful verification
        """
        try:
            html_template = self.create_welcome_html_template(recipient_name)
            
            payload = {
                "from": {
                    "address": self.sender_email,
                    "name": self.sender_name
                },
                "to": [{
                    "email_address": {
                        "address": recipient_email,
                        "name": recipient_name
                    }
                }],
                "subject": f"🎉 Welcome to MyDSCVR, {recipient_name}! Your Dubai Adventure Begins",
                "htmlbody": html_template
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                logger.info(f"✅ Welcome email sent successfully to {recipient_email}")
                return {
                    "success": True,
                    "message": "Welcome email sent successfully",
                    "response": response.json()
                }
            else:
                logger.error(f"❌ Failed to send welcome email: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Email service error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception sending welcome email: {e}")
            return {
                "success": False,
                "error": "Email service exception",
                "details": str(e)
            }

    async def send_password_reset_email(
        self, 
        recipient_email: str, 
        recipient_name: str, 
        reset_code: str,
        expires_in_minutes: int = 15
    ) -> Dict[str, Any]:
        """
        Send password reset email
        """
        try:
            html_template = self.create_password_reset_html_template(
                user_name=recipient_name,
                reset_code=reset_code,
                expires_in_minutes=expires_in_minutes
            )
            
            payload = {
                "from": {
                    "address": self.sender_email,
                    "name": self.sender_name
                },
                "to": [{
                    "email_address": {
                        "address": recipient_email,
                        "name": recipient_name
                    }
                }],
                "subject": f"🔐 MyDSCVR Password Reset Code: {reset_code}",
                "htmlbody": html_template
            }
            
            response = requests.post(
                self.api_url,
                headers=self.headers,
                data=json.dumps(payload)
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"✅ Password reset email sent successfully to {recipient_email}")
                return {
                    "success": True,
                    "message": "Password reset email sent successfully",
                    "response": response.json()
                }
            else:
                logger.error(f"❌ Failed to send password reset email: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"Email service error: {response.status_code}",
                    "details": response.text
                }
                
        except Exception as e:
            logger.error(f"❌ Exception sending password reset email: {e}")
            return {
                "success": False,
                "error": "Email service exception",
                "details": str(e)
            }


# Initialize email service instance
email_service = ZeptoMailService()