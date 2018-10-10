"""
Purpose: Set default values for system-wides settings.  Defaults for most settings
are loaded from environment variables.
"""
import os

# Defaults
# -----------------------------------------------------------------------------

BCDC_PACKAGE_OWNER_ORG_ID = "d5316a1b-2646-4c19-9671-c12231c4ec8b" #Ministry of Jobs, Tourism and Skills Training
BCDC_PACKAGE_OWNER_SUB_ORG_ID = "c1222ef5-5013-4d9a-a9a0-373c54241e77" #DataBC

# Load application settings from environment variables
# -----------------------------------------------------------------------------

#
# Logging
#

if not "LOG_LEVEL" in os.environ:
  LOG_LEVEL = "WARN"
else:
  LOG_LEVEL = os.environ['LOG_LEVEL']

#
# BC Data Catalog
#

#The base URL for BCDC (e.g. https://catalogue.data.gov.bc.ca)
if not "BCDC_BASE_URL" in os.environ:
  raise ValueError("Missing 'BCDC_BASE_URL' environment variable.")
else:
  BCDC_BASE_URL = os.environ['BCDC_BASE_URL']

#The path after the base URL on which the BCDC REST API is accessible
if not "BCDC_API_PATH" in os.environ:
  raise ValueError("Missing 'BCDC_API_PATH' environment variable.")
else:
  BCDC_API_PATH = os.environ['BCDC_API_PATH']

#The key use for all access to the BCDC REST API
if not "BCDC_API_KEY" in os.environ:
  raise ValueError("Missing 'BCDC_API_KEY' environment variable.")
else:
  BCDC_API_KEY = os.environ['BCDC_API_KEY']

#The group that all new metadata records will be added to
if not "BCDC_GROUP_ID" in os.environ:
  raise ValueError("Missing 'BCDC_GROUP_ID' environment variable.")
else:
  BCDC_GROUP_ID = os.environ['BCDC_GROUP_ID']

#Default organization to list as the owner for new metadata records 
if not "BCDC_PACKAGE_OWNER_ORG_ID" in os.environ: 
  raise ValueError("Missing 'BCDC_PACKAGE_OWNER_ORG_ID' environment variable.")
else:
  BCDC_PACKAGE_OWNER_ORG_ID = os.environ['BCDC_PACKAGE_OWNER_ORG_ID']

#Default sub-organization to list as the owner for new metadata records 
if not "BCDC_PACKAGE_OWNER_SUB_ORG_ID" in os.environ:
  raise ValueError("Missing 'BCDC_PACKAGE_OWNER_SUB_ORG_ID' environment variable.")
else:
  BCDC_PACKAGE_OWNER_SUB_ORG_ID = os.environ['BCDC_PACKAGE_OWNER_SUB_ORG_ID']

#
# Notification Emails
#

#The SMTP server to use for sending notification emails when new APIs are registered
if not "SMTP_SERVER" in os.environ:
  raise ValueError("Missing 'SMTP_SERVER' environment variable.  Must specify which server to use for sending emails.")
else:
  SMTP_SERVER = os.environ['SMTP_SERVER']

#The port used to access the SMTP server
if not "SMTP_PORT" in os.environ:
  raise ValueError("Missing 'SMTP_PORT' environment variable.  Must specify the port to send emails through the SMTP server.")
else:
  SMTP_PORT = os.environ['SMTP_PORT']

#The email address from which all notification emails will be sent
if not "FROM_EMAIL_ADDRESS" in os.environ:
  raise ValueError("Missing 'FROM_EMAIL_ADDRESS' environment variable.")
else:
  FROM_EMAIL_ADDRESS = os.environ['FROM_EMAIL_ADDRESS']

#The password for the account from which all notification emails will be sent
if not "FROM_EMAIL_PASSWORD" in os.environ:
  raise ValueError("Missing 'FROM_EMAIL_PASSWORD' environment variable.")
else:
  FROM_EMAIL_PASSWORD = os.environ['FROM_EMAIL_PASSWORD']

#A comma-separated list of email addresses which will receive notifications about newly 
#registered APIs
if not "TARGET_EMAIL_ADDRESSES" in os.environ:
  raise ValueError("Missing 'TARGET_EMAIL_ADDRESSES' environment variable. Must specify a csv list of email addresses.")
else:
  TARGET_EMAIL_ADDRESSES = os.environ['TARGET_EMAIL_ADDRESSES']