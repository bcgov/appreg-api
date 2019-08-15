# kq-api
REST API that supports the API Key Request (KQ) application

This API supports the following endpoints:
```
  GET  /                    OpenAPI specification (returns application/json)
  POST /request_key         Accepts a form submission requesting a new API key, and sends a verification email to the user (returns application/json)
  GET  /verify_key_request  Confirm the request details.  A link to this resource is sent in the verification email (returns text/html)
  GET  /status              Gets the status of a key request associated with a given verification code
  POST /challenge           Creates a new "challenge" (challenge's support captchas) and returns its ID (returns application/json)
  GET  /challenge/<challenge-id>.png
                            Gets a captcha image showing the secret text of the challenge
Note: the two challenge resources are intended to support captchas.  A valid 
challenge ID and challenge secret must be submitted in the POST /request_key 
body in order for the request to be valid.
```

## Dependencies

The application depends on two Redis databases which should be made 
accessible to this application. The two databases are:

  - Key request store: This Redis database keeps a temporary record of
    all API key requests.  This is needed because requesting an API key is
    a two step process (step 1: fill out the request form; step 2: verify 
    the request via a verification email).  There is a time delay between 
    when a user performs these steps, so the API key request is temporarily 
    stored in the interim.
  - Challenge store: This Redis database keeps a temporary record of all
    "challenges" (challenges are used to support captchas).  There is a
    time delay between when a captcha is generated and when it is viewed
    (and "answered") by a user, so the underlying "challenge" is stored 
    in the interim.

The two Redis databases can each be run from a separate instance, or they could
be run from the same instance.  The Redis docs suggest separate instances are generally
preferred.

Ideally both Redis databases will be configured to persist their contents to the
file system.  This will ensure robust handling of API key requests that straddle 
system restarts.

A docker-compose.yml file is included to launch two the above two Redis databases.

```
docker-compose up -d
```

(You may wish to run the Redis databases in some other way without docker-compose.  
That's okay too.)

## Run in docker

  docker build -t kq-api .
  docker run -p8000:8000 --rm --env-file .env kq-api

...where the file .env contains appropriate values for all of the environment 
variables listed below.

### Application environment

The application reads all its application settings from environment variables.  
The following environment variables are supported:

```
#Values: ERROR, WARN, INFO, DEBUG
LOG_LEVEL 

#Base url of the BC Data Catalog.  e.g. "https://cad.data.gov.bc.ca"
BCDC_BASE_URL
#Relative path of BC Data Catalog API.  e.g. "/api/3"
BCDC_API_PATH
#The BC Data Catalog API Key to be used for creating new metadata records
BCDC_API_KEY

#The organization that new metadata records will be initially associated with
BCDC_PACKAGE_OWNER_ORG_ID
#The sub-organization that new metadata records will be initially associated with
BCDC_PACKAGE_OWNER_SUB_ORG_ID

#The SMTP server to send notification emails through.  e.g. apps.smtp.gov.bc.ca
SMTP_SERVER
#The SMTP server port to use.  e.g. 587
SMTP_PORT
#The "sender" email address from notification emails. e.g. data@gov.bc.ca
FROM_EMAIL_ADDRESS
#The password for the FROM_EMAIL_ADDRESS account.
FROM_EMAIL_PASSWORD
#A csv list of recipient email addresses for notification emails.
TARGET_EMAIL_ADDRESSES

#The Redis URL for the key request store. e.g. redis://:@localhost:6379/0
# This is where API key requests will be temporarily stored between the time
# the request is made and when the user validates the request (via a link in an 
#email)
KQ_STORE_URL
#The number of seconds that API key requests will be held in the key request store.  
# e.g. 432000 is 5 days
KQ_STORE_TTL_SECONDS

#The Redis URL for the challenge store. e.g. "redis://:@localhost:6389/0"
# This is where the "challenges" will be temporarily stored.
# Challenges are a key-value pair which record a challenge ID and its 
# secret text (key is challenge ID, value is challenge secret).
# "Challenges" are used to generate captchas and verify user responses
# to captchas.
CAPTCHA_STORE_URL
#The number of seconds that "challenges" will be held in the challenge store.  
# e.g. 432000 is 5 days
CAPTCHA_STORE_TTL_SECONDS

#The publically-accessible URL that can be used to access this API.
# The URL must be public because it will be used to construct a key request 
# validation URL that will be sent to the user via email.  e.g. http://<host>:<port>/kq
KQ_API_URL

#This parameter is only to be used in development or test environments.  Its 
# purpose is to enable the POST /challenge endpoint to return both the challenge ID
# and the challenge secret (normally the challenge secret is not sent to the user).
# By sending the challenge secret in the response, we allow a machine to perform
# all steps of the key request process, bypassing the need for a human to look at 
# the captcha.  This allows allows automated tests to run without human intervention.
# To enable, set the value to 1.  Default is 0 (disabled).  
ALLOW_TEST_MODE

```

If the application is run in a docker container, the above environment variables
must be injected into the container on startup.
