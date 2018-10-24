import smtplib
from email.mime.text import MIMEText

SECURE_PORTS = [465, 587]

def send_email(to, bcc=None, email_subject="", email_body="", smtp_server=None, smtp_port=587, from_email_address=None, from_password=None):
  """
  Sends an email
  :param to: a list of email addresses to send to
  :param bcc: a list of email addresses to bcc
  :email_subject: the subject line of the email
  :email_body: the content body of the email
  :smtp_server: the SMTP server to use
  :from_email_address: the email address to send from
  :from_password: the password of the email account to send from
  """

  if not to:
    raise ValueError("precondition failed.  'to' must not be None")
  if not from_email_address:
    raise ValueError("precondition failed.  'from_email_address' must not be None")
  if not smtp_server:
    raise ValueError("precondition failed.  'smtp_server' must not be None")
  
  if not bcc:
    bcc = []

  smtp_port = int(smtp_port)

  msg = MIMEText(email_body, "html")
  msg["From"] = from_email_address
  msg["To"] = ",".join(to)
  msg["Subject"] = email_subject

  s = None
  if smtp_port in SECURE_PORTS:
    s = smtplib.SMTP_SSL(smtp_server, smtp_port)
    try:
      s.login(from_email_address, from_password)
    except smtplib.SMTPAuthenticationError as e:
      raise ValueError("Unable to login to SMPT server.  Invalid credentials.")
  else:
    s = smtplib.SMTP(smtp_server, smtp_port)

  try:
    s.sendmail(from_email_address, to + bcc, msg.as_string())
  except smtplib.SMTPRecipientsRefused as e:
    raise ValueError(e)
  s.quit()