"""
Purpose: Set default values for system-wides settings.  Defaults for most settings
are loaded from environment variables.
"""
import os

# Defaults
# -----------------------------------------------------------------------------

BCDC_PACKAGE_OWNER_ORG_ID = "d5316a1b-2646-4c19-9671-c12231c4ec8b" #Ministry of Jobs, Tourism and Skills Training
BCDC_PACKAGE_OWNER_SUB_ORG_ID = "c1222ef5-5013-4d9a-a9a0-373c54241e77" #DataBC
STORE_TTL_SECONDS = 86400 #one day
ALLOW_TEST_MODE = False

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

#
# Data stores
#

#The URL of the Redis database used for key requests
if not "KQ_STORE_URL" in os.environ:
  raise ValueError("Missing 'KQ_STORE_URL' environment variable. Must specify a Redis url.")
else:
  KQ_STORE_URL = os.environ['KQ_STORE_URL']

#The time-to-live (TTL) in seconds for persisted API Key Requests. Once TTL expires, the request will be erased
#whether or not is has been verified.
if "KQ_STORE_TTL_SECONDS" in os.environ:
  KQ_STORE_TTL_SECONDS = os.environ['KQ_STORE_TTL_SECONDS']

#The URL of the Redis database used for captchas
if not "CAPTCHA_STORE_URL" in os.environ:
  raise ValueError("Missing 'CAPTCHA_STORE_URL' environment variable. Must specify a Redis url.")
else:
  CAPTCHA_STORE_URL = os.environ['CAPTCHA_STORE_URL']

#The time-to-live (TTL) in seconds for captchas
if "CAPTCHA_STORE_TTL_SECONDS" in os.environ:
  CAPTCHA_STORE_TTL_SECONDS = os.environ['CAPTCHA_STORE_TTL_SECONDS']

#
# This API's URL
#

#The URL that this API will be publically accessible at.
if not "KQ_API_URL" in os.environ:
  raise ValueError("Missing 'KQ_API_URL' environment variable. Must specify the URL that this API will be publically accessible at.")
else:
  KQ_API_URL = os.environ['KQ_API_URL']

#
# Other
#

#Test mode
if "ALLOW_TEST_MODE" in os.environ:
  ALLOW_TEST_MODE = os.environ['ALLOW_TEST_MODE'].upper() in ["T", "1", "TRUE"]
