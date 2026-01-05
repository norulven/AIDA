"""Mail client operations for Aida using IMAP and SMTP."""

import imaplib
import smtplib
import email
import logging
from email.mime.text import MIMEText
from email.header import decode_header
from typing import List, Dict, Optional

from src.core.config import MailConfig

# Configure logging
logger = logging.getLogger("aida.mail")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler('/tmp/aida_mail.log')
    fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)

class MailClient:
    """Handles IMAP and SMTP connections for email operations."""

    def __init__(self, config: MailConfig):
        self.config = config
        self.imap_conn: Optional[imaplib.IMAP4_SSL] = None
        self.smtp_conn: Optional[smtplib.SMTP_SSL] = None
        logger.info("MailClient initialized.")

    def _ensure_imap_connected(self) -> bool:
        """Ensures IMAP connection is active and logged in."""
        if not self.config.enabled:
            logger.warning("Mail integration is not enabled in config.")
            return False
        if not self.config.email or not self.config.password:
            logger.error("Email credentials not set.")
            return False

        try:
            if self.imap_conn:
                try:
                    self.imap_conn.noop() # Check if connection is alive
                    return True
                except imaplib.IMAP4.error:
                    logger.warning("IMAP connection lost, reconnecting...")
                    self.disconnect_imap()

            logger.info(f"Connecting to IMAP server: {self.config.imap_server}:{self.config.imap_port}")
            self.imap_conn = imaplib.IMAP4_SSL(self.config.imap_server, self.config.imap_port)
            self.imap_conn.login(self.config.email, self.config.password)
            logger.info("IMAP connected and logged in.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect or login to IMAP: {e}", exc_info=True)
            self.disconnect_imap()
            return False

    def disconnect_imap(self) -> None:
        """Disconnects from IMAP server."""
        if self.imap_conn:
            try:
                self.imap_conn.logout()
                logger.info("IMAP disconnected.")
            except Exception as e:
                logger.warning(f"Error during IMAP logout: {e}")
            finally:
                self.imap_conn = None

    def _ensure_smtp_connected(self) -> bool:
        """Ensures SMTP connection is active and logged in."""
        if not self.config.enabled:
            logger.warning("Mail integration is not enabled in config.")
            return False
        if not self.config.email or not self.config.password:
            logger.error("Email credentials not set.")
            return False

        try:
            if self.smtp_conn:
                try:
                    # Check if connection is alive and authenticated (might not be a simple noop)
                    # For simplicity, we'll assume if it's not None it's mostly good
                    pass
                except Exception: # More robust check might be needed for some SMTP servers
                    logger.warning("SMTP connection might be stale, reconnecting...")
                    self.disconnect_smtp()

            logger.info(f"Connecting to SMTP server: {self.config.smtp_server}:{self.config.smtp_port}")
            self.smtp_conn = smtplib.SMTP_SSL(self.config.smtp_server, self.config.smtp_port)
            self.smtp_conn.login(self.config.email, self.config.password)
            logger.info("SMTP connected and logged in.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect or login to SMTP: {e}", exc_info=True)
            self.disconnect_smtp()
            return False

    def disconnect_smtp(self) -> None:
        """Disconnects from SMTP server."""
        if self.smtp_conn:
            try:
                self.smtp_conn.quit()
                logger.info("SMTP disconnected.")
            except Exception as e:
                logger.warning(f"Error during SMTP quit: {e}")
            finally:
                self.smtp_conn = None

    def get_unread_emails(self, limit: int = 3) -> List[Dict]:
        """Fetches and returns summary of latest unread emails."""
        emails_summary = []
        if not self._ensure_imap_connected():
            return []

        try:
            self.imap_conn.select('INBOX')
            status, email_ids = self.imap_conn.search(None, 'UNSEEN')
            
            if status != 'OK':
                logger.error(f"IMAP search failed: {status}")
                return []

            email_id_list = email_ids[0].split()
            # Get latest emails
            for num in email_id_list[-limit:]:
                status, msg_data = self.imap_conn.fetch(num, '(RFC822)')
                if status != 'OK':
                    logger.error(f"IMAP fetch failed for ID {num}: {status}")
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                
                # Decode header for sender and subject
                sender_header = decode_header(msg['From'])
                sender = sender_header[0][0].decode(sender_header[0][1] or 'utf-8') if sender_header[0][1] else sender_header[0][0]
                
                subject_header = decode_header(msg['Subject'])
                subject = subject_header[0][0].decode(subject_header[0][1] or 'utf-8') if subject_header[0][1] else subject_header[0][0]
                
                emails_summary.append({
                    "from": sender,
                    "subject": subject,
                    "date": msg['Date'],
                    "body_snippet": self._get_email_body_snippet(msg),
                })
            logger.info(f"Fetched {len(emails_summary)} unread emails.")
            return emails_summary

        except Exception as e:
            logger.error(f"Error fetching unread emails: {e}", exc_info=True)
            return []
        finally:
            self.disconnect_imap() # Always disconnect after operation

    def _get_email_body_snippet(self, msg) -> str:
        """Extracts a plain text snippet from the email body."""
        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                cdispo = str(part.get('Content-Disposition'))

                # Look for plain text parts that are not attachments
                if ctype == 'text/plain' and 'attachment' not in cdispo:
                    try:
                        body = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
                        return body[:200] + "..." if len(body) > 200 else body
                    except Exception:
                        pass
        else:
            if msg.get_content_type() == 'text/plain':
                try:
                    body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8')
                    return body[:200] + "..." if len(body) > 200 else body
                except Exception:
                    pass
        return "No plain text body found."

    def send_email(self, to_address: str, subject: str, body: str) -> bool:
        """Sends an email."""
        if not self._ensure_smtp_connected():
            return False

        try:
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['From'] = self.config.email
            msg['To'] = to_address
            msg['Subject'] = subject

            self.smtp_conn.send_message(msg)
            logger.info(f"Email sent to {to_address} with subject '{subject}'.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
            return False
        finally:
            self.disconnect_smtp() # Always disconnect after operation
