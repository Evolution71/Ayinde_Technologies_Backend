"""
Email utilities for Ayinde Technologies
Handles sending confirmation emails via Gmail SMTP
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class EmailSender:
    """Send emails via Gmail SMTP"""

    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("GMAIL_EMAIL", "")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD", "")
        self.enabled = bool(self.sender_email and self.sender_password)

        if self.enabled:
            logger.info(f"✅ Email system initialized with: {self.sender_email}")
        else:
            logger.warning("⚠️ Email system not configured. Set GMAIL_EMAIL and GMAIL_APP_PASSWORD environment variables.")

    def send_order_confirmation(
        self,
        to_email: str,
        full_name: str,
        tier_name: str,
        amount: float,
        order_id: int,
        service_type: str,
        transaction_id: str,
        service_starts_at: str,
        service_ends_at: str
    ) -> bool:
        """Send order confirmation email"""

        if not self.enabled:
            logger.warning(f"Email not sent to {to_email} - email system not configured")
            return False

        try:
            subject = f"✅ Payment Successful - Order #{order_id}"

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%); color: white; padding: 20px; border-radius: 8px; text-align: center; }}
                        .content {{ background: #f8fafc; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                        .order-details {{ background: white; padding: 15px; border-left: 4px solid #1e40af; margin: 15px 0; }}
                        .detail-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #e0e7ff; }}
                        .detail-row:last-child {{ border-bottom: none; }}
                        .label {{ font-weight: bold; color: #1e40af; }}
                        .value {{ text-align: right; }}
                        .success {{ color: #16a34a; font-weight: bold; font-size: 18px; }}
                        .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>Welcome to Ayinde Technologies!</h1>
                            <p class="success">✅ Your Payment is Successful</p>
                        </div>

                        <div class="content">
                            <p>Hi <strong>{full_name}</strong>,</p>
                            <p>Thank you for choosing Ayinde Technologies! Your payment has been processed successfully and your service is now active.</p>

                            <div class="order-details">
                                <h3 style="margin-top: 0; color: #1e40af;">Order Details</h3>
                                <div class="detail-row">
                                    <span class="label">Order ID:</span>
                                    <span class="value">#{order_id}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Service Package:</span>
                                    <span class="value">{tier_name}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Service Type:</span>
                                    <span class="value">{service_type.capitalize()}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Amount Charged:</span>
                                    <span class="value">${amount:.2f}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Transaction ID:</span>
                                    <span class="value">{transaction_id}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Service Starts:</span>
                                    <span class="value">{service_starts_at}</span>
                                </div>
                                <div class="detail-row">
                                    <span class="label">Service Ends:</span>
                                    <span class="value">{service_ends_at}</span>
                                </div>
                            </div>

                            <p>Your service is now active and ready to use. You can access your account anytime on our website.</p>

                            <p><strong>Next Steps:</strong></p>
                            <ul>
                                <li>Log in to your account to access your service dashboard</li>
                                <li>Review the features included in your package</li>
                                <li>Contact our support team if you have any questions</li>
                            </ul>

                            <p>If you have any questions or need assistance, please don't hesitate to contact our support team at <strong>support@ayindetechnologies.com</strong></p>

                            <p>Best regards,<br><strong>Ayinde Technologies Team</strong></p>
                        </div>

                        <div class="footer">
                            <p>© 2026 Ayinde Technologies. All rights reserved.</p>
                            <p>This is an automated email. Please do not reply to this email address.</p>
                        </div>
                    </div>
                </body>
            </html>
            """

            return self._send_email(to_email, subject, html_content)

        except Exception as e:
            logger.error(f"Error sending order confirmation email: {str(e)}")
            return False

    def send_payment_failed_notification(
        self,
        to_email: str,
        full_name: str,
        tier_name: str,
        reason: str
    ) -> bool:
        """Send payment failed notification"""

        if not self.enabled:
            return False

        try:
            subject = f"❌ Payment Failed - {tier_name}"

            html_content = f"""
            <html>
                <head>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background: #fee2e2; color: #991b1b; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #dc2626; }}
                        .content {{ background: #f8fafc; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>❌ Payment Failed</h1>
                        </div>

                        <div class="content">
                            <p>Hi <strong>{full_name}</strong>,</p>
                            <p>Unfortunately, your payment for <strong>{tier_name}</strong> could not be processed.</p>

                            <h3>Reason:</h3>
                            <p><strong>{reason}</strong></p>

                            <p><strong>What you can do:</strong></p>
                            <ul>
                                <li>Check that your card details are correct</li>
                                <li>Ensure you have sufficient funds</li>
                                <li>Try a different card or payment method</li>
                                <li>Contact your bank to check for any restrictions</li>
                                <li>Retry the payment on our website</li>
                            </ul>

                            <p>If you continue to experience issues, please contact our support team at <strong>support@ayindetechnologies.com</strong></p>

                            <p>Best regards,<br><strong>Ayinde Technologies Team</strong></p>
                        </div>
                    </div>
                </body>
            </html>
            """

            return self._send_email(to_email, subject, html_content)

        except Exception as e:
            logger.error(f"Error sending payment failed notification: {str(e)}")
            return False

    def _send_email(self, to_email: str, subject: str, html_content: str) -> bool:
        """Internal method to send email via SMTP"""

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = to_email

            # Attach HTML content
            part = MIMEText(html_content, "html")
            msg.attach(part)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)

            logger.info(f"✅ Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
            return False


# Global email sender instance
email_sender = EmailSender()