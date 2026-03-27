import logging
import smtplib
from email.message import EmailMessage
import os

logger = logging.getLogger("geoai.email")

def send_pdf_email(email_to: str, subject: str, body: str, pdf_bytes: bytes, filename: str = "Report.pdf"):
    """
    Sends an email with a PDF attachment.
    If SMTP variables are not set, it mocks the sending process.
    """
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    
    if not smtp_server or not smtp_user or not smtp_pass:
        msg = "Email delivery MOCKED. To enable real emails, configure SMTP_SERVER, SMTP_USER, and SMTP_PASS in your environment."
        logger.warning(msg)
        return {"status": "success", "message": msg, "mocked": True}
        
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = email_to
        msg.set_content(body)
        
        msg.add_attachment(pdf_bytes, maintype='application/pdf', subtype='pdf', filename=filename)
        
        with smtplib.SMTP(smtp_server, int(smtp_port)) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            
        logger.info(f"Email sent successfully to {email_to}")
        return {"status": "success", "message": "Email sent successfully"}
    except Exception as e:
        logger.error(f"Failed to send email to {email_to}: {str(e)}")
        raise e
