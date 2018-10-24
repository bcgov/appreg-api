from flask import Flask, Response, jsonify, request, redirect, url_for, g, send_file
from . import settings
from . import bcdc
from . import html_templates as html
from .emailer import send_email
from .challenge_store import ChallengeStore
from .request_store import RequestStore
from profanityfilter import ProfanityFilter
import os
import json
import requests
import logging
from flask_cors import CORS

#------------------------------------------------------------------------------
# Init
#------------------------------------------------------------------------------

app = Flask(__name__)

#In debug mode add CORS headers to responses. (When not in debug mode, it is 
#assumed that CORS headers will be controlled externally, such as by a reverse
#proxy)
if "FLASK_DEBUG" in os.environ and os.environ["FLASK_DEBUG"]:
  CORS(app)

#setup data stores
kq_store = RequestStore(app, db_url=settings.KQ_STORE_URL, default_ttl_seconds=settings.KQ_STORE_TTL_SECONDS)
challenge_store = ChallengeStore(app, db_url=settings.CAPTCHA_STORE_URL, default_ttl_seconds=settings.CAPTCHA_STORE_TTL_SECONDS)

#setup logging
app.logger.setLevel(getattr(logging, settings.LOG_LEVEL)) #main logger's level

#inject some initial log messages
app.logger.info("Initializing {}".format(__name__))
app.logger.info("Log level is '{}'".format(settings.LOG_LEVEL))

profanity_filter = ProfanityFilter()

#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

API_SPEC_FILENAME = os.path.join(app.root_path, "../docs/kq-api.openapi3.json")
STATUS_KEY = "kq_status"
PROCESSING_STATES = {
  "AWAITING_VERIFICATION": "awaiting verification",
  "VERIFIED": "verified"
}

#------------------------------------------------------------------------------
# API Endpoints
#------------------------------------------------------------------------------

@app.route('/')
def api():
  """
  Summary information about this API
  """
  apiBaseUrl = request.url_root.rstrip("/")

  with open(API_SPEC_FILENAME) as f:
    s = f.read()
    s = s.replace("${HOST}", apiBaseUrl)
    r = Response(response=s, mimetype='application/json', status=200)
    return r

@app.route('/request_key', methods=["POST"])
def request_key():
  """
  Create a new request for an API key
  """

  #headers
  contentType = request.headers.get('Content-Type')

  #check content type of request req_data
  if not contentType or contentType != "application/json":
    return jsonify({"msg": "Invalid Content-Type.  Expecting application/json"}), 400

  #get request body
  try:
    req_data = request.get_json()
  except Exception as e:
    print(e)
    return jsonify({"msg": "request body is not valid json"}), 400

  #validate the request body
  try:
    req_data = clean_and_validate_req_data(req_data)
  except ValueError as e:
    return jsonify({"msg": "{}".format(e)}), 400
  except RuntimeError as e:
    app.logger.error("{}".format(e));
    return jsonify({"msg": "An unexpected error occurred while validating the API key request."}), 500
 
  #check for bad language in request body
  app.logger.info("check bad language")
  try:
    check_bad_language(req_data)
  except ValueError as e:
    return jsonify({"msg": "{}".format(e)}), 400

  #save the API key request and generate a verification code
  try:
    verification_code = kq_store.save_request(req_data)
  except RuntimeError as e:
    app.logger.error("Unable to save request. {}".format(e))
    return jsonify({"msg": "Server error.  Unable to record API key request."}), 500

  #send the verification code to the user
  try:
    send_verification_email_to_submitter(req_data, verification_code)
  except Exception as e: 
    app.logger.error("Unable to send verification email for new API. {}".format(e))
    return jsonify({"msg": "Server error.  Unable to record API key request."}), 500

  success_resp = {
    "verification_code": verification_code
  }

  return jsonify(success_resp), 200

@app.route('/verify_key_request', methods=["GET"])
def verify_key_request():
  """
  Accepts a veritication code.  Checks that the code corresponds to an active API Key Request.  If so
  the request is verified and processing of it is initiated:
  Returns a text/html response
  """
  app.logger.info("verify_key_request message received")
  verification_code = request.args.get('verification_code')
  
  try:
    req_data = kq_store.load_request(verification_code)
  except RuntimeError as e:
    app.logger.error("Unable to access request from store. {}".format(e))
    return html.get_err_verify_key_request_store(), 500

  if not req_data:
    return html.get_err_verify_key_request_invalid_code(), 404

  if req_data[STATUS_KEY]["state"] != PROCESSING_STATES["AWAITING_VERIFICATION"]:
    return html.get_err_verify_key_request_already_done(), 400

  metadata_web_url = None
  #create a draft metadata record (if one doesn't exist yet)
  if not req_data["app"].get("metadata_url"):
    package = None
    try:
      package = create_package(req_data)
      if not package:
        raise ValueError("Unknown reason")
      #add a status object to the request data.  the updated request data will
      #be saved back to the store (below) for a brief period of time.
      new_metadata_record_details = {
        "package_id": package["id"],
        "metadata_web_url": bcdc.package_id_to_web_url(package["id"]),
        "metadata_api_url": bcdc.package_id_to_api_url(package["id"])
      }
      req_data[STATUS_KEY]["new_metadata_record"] = new_metadata_record_details
    except ValueError as e: #user input errors cause HTTP 400
      return html.get_err_create_metadata(e), 400
    except RuntimeError as e: #unexpected system errors cause HTTP 500
      app.logger.error("Unable to create metadata record in the BC Data Catalog. {}".format(e))
      return html.get_err_create_metadata(), 500

    try:
      create_app_resource(package["id"], req_data)
    except ValueError as e: #perhaps other errors are possible too??  if so, catch those too
      app.logger.warn("Unable to create app root resource associated with the new metadata record. {}".format(e))

  send_notification_email_to_admin(req_data)

  req_data[STATUS_KEY]["state"] = PROCESSING_STATES["VERIFIED"]

  send_notification_email_to_submitter(req_data)

  kq_store.save_request(req_data, verification_code=verification_code)

  return html.get_verify_key_request_success(req_data), 200

@app.route('/status', methods=["GET"])
def get_status():
  """
  Gets a json object which summarizes the processing status of the API Key Request
  associated with a given verification code.  The status is only available for a certain 
  amount of time (STATUS_TTL_SECONDS) after the a request is verified .  
  After that the status is deleted.
  """
  app.logger.info("verify_key_request message received")
  verification_code = request.args.get('verification_code')
  
  try:
    req_data = kq_store.load_request(verification_code)
  except RuntimeError as e:
    app.logger.error("Unable to access request from store. {}".format(e))
    return jsonify({"msg": "Server error.  Unable to access status of API key request."}), 500

  if not req_data:
    return jsonify({"msg": "Unknown verification code"}), 404
  
  if not STATUS_KEY in req_data:
    return jsonify({"msg": "Unable to find status of this request"}), 500

  status = req_data[STATUS_KEY]
  return jsonify(status), 200
  
@app.route('/challenge', methods=["POST"])
def new_challenge():
  """
  Creates a new random challenge and saves it server-side for 5 days.  
  A challenge has an public ID (shared with the user)
  and a SECRET (not shared with the user, except in TEST MODE).  
  This challenge endpoint is provided to support captchas.  There is a companion endpoint:
    /challenge/<id>.png which generates a captcha image for the given challenge id.
  The /request_key requires the user to submit a valid challenge_id and secret.  The secret 
  will generally be determine by the user looking at the captcha image, although there is another
  option for use in a development or testing environment:
  The request body, if specified (application/json), may contain one parameter: 
    'include_secret': <boolean>
  This parameter indicates that the response should include the secret.  This is useful
  in a test environment to support automated test cases, but is not a good idea in a
  production environment.  The application setting "ALLOW_TEST_MODE" must be explicitly 
  set to True (or 1) to allow the 'include_secret' parameter to be respected.
  Response format (application/json):
    {
      "challenge_id": "ID HERE"
    }
  """
  include_secret = False

  #check optional request body.
  contentType = request.headers.get('Content-Type')
  if contentType and contentType == "application/json":
    try:
      data = request.get_json()
      include_secret = data.get('include_secret', False)
    except Exception as e:
      pass

  try:
    challenge = challenge_store.new_challenge()
    print(challenge)
  except RuntimeError as e:
    app.logger.error("Unable to create new challenge. {}".format(e))
    return jsonify({"msg": "Unable to create new challenge"}), 500

  resp_success = {
    "challenge_id": challenge["challenge_id"]
  }
  if settings.ALLOW_TEST_MODE and include_secret:
    resp_success["secret"] = challenge["secret"]
    app.logger.warn("Challenge secret sent in /challenge response because 'TEST MODE' is active.  This may be suitable for a test environment, but is a security risk in a production environment.")

  return jsonify(resp_success), 200

@app.route('/challenge/<challenge_id>.png', methods=["GET"])
def get_captcha_image(challenge_id):
  """
  Gets a captcha image correspondong to a given challenge id.  The
  text of the captcha image will show the challenge's secret.
  """
  if not challenge_id:
    return jsonify({"msg": "Not found"}), 404

  captcha_bytes = challenge_store.challenge_id_to_captcha(challenge_id)
  return send_file(captcha_bytes, mimetype='image/png')

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def check_bad_language(req_data):
  """
  Checks for profanity in the request object
  If any problems is found, raises a ValueError with a description.  
  Otherwise returns None if no problems.
  """
  app.logger.info("check bad language")
  app.logger.info(req_data["app"]["title"])
  app.logger.info(profanity_filter.is_profane(req_data["app"]["title"]))
  if profanity_filter.is_profane(req_data["app"]["title"]):
    raise ValueError("Inappropriate language found in the application's title.")  

  if profanity_filter.is_profane(req_data["app"]["description"]):
    raise ValueError("Inappropriate language found in the application's description.")
  
  return None

def clean_and_validate_req_data(req_data):

  #ensure req_data object hierarchy exists
  #---------------------------------------
  if not req_data:
    req_data = {}
  if not req_data.get("api"):
    req_data["api"] = {}
  if not req_data.get("app"):
    req_data["app"] = {}
  if not req_data["app"].get("owner"):
    req_data["app"]["owner"] = {}
  if not req_data["app"].get("security"):
    req_data["app"]["security"] = {}
  if not req_data["app"].get("license"):
    req_data["app"]["license"] = {}
  if not req_data["app"]["owner"].get("contact_person"):
    req_data["app"]["owner"]["contact_person"] = {}
  if not req_data.get("submitted_by_person"):
    req_data["submitted_by_person"] = {}
  if not req_data.get("challenge"):
    req_data["challenge"] = {}

  #check that required fields are present
  #--------------------------------------
  if not req_data["api"].get("title"):
    raise ValueError("Missing '$.api.title'")

  if not req_data["app"].get("title"):
    raise ValueError("Missing '$.app.title'")
  if not req_data["app"].get("description"):
    raise ValueError("Missing '$.app.description'")
  if not req_data["app"].get("url"):
    raise ValueError("Missing '$.app.url'")
  if not req_data["app"].get("type"):
    raise ValueError("Missing '$.app.type'")
  if not req_data["app"].get("status"):
    raise ValueError("Missing '$.app.status'")

  if not req_data["app"]["owner"].get("org_id"):
    raise ValueError("Missing '$.app.owner.org_id'")
  
  if not req_data["app"]["owner"]["contact_person"].get("name"):
    raise ValueError("Missing '$.app.owner.contact_person.name'")
  if not req_data["app"]["owner"]["contact_person"].get("business_email"):
    raise ValueError("Missing '$.app.owner.contact_person.business_email'") 

  if not req_data["app"]["security"].get("download_audience"):
    raise ValueError("Missing '$.app.security.download_audience'")
  if not req_data["app"]["security"].get("view_audience"):
    raise ValueError("Missing '$.app.security.view_audience'")
  if not req_data["app"]["security"].get("metadata_visibility"):
    raise ValueError("Missing '$.app.security.metadata_visibility'")
  if not req_data["app"]["security"].get("security_class"):
    raise ValueError("Missing '$.app.security.security_class'")

  if not req_data["app"]["license"].get("license_id"):
    raise ValueError("Missing '$.app.license.license_id'")

  if not req_data["submitted_by_person"].get("name"):
    raise ValueError("Missing '$.submitted_by_person.name'")
  if not req_data["submitted_by_person"].get("org_id") and not req_data["submitted_by_person"].get("org_name"):
    raise ValueError("Missing one of '$.submitted_by_person.org_id' or '$submitted_by_person.org_name'")
  if not req_data["submitted_by_person"].get("business_email"):
    raise ValueError("Missing '$.submitted_by_person.business_email'")

  if not req_data["challenge"].get("id"):
    raise ValueError("Missing '$.challenge.id'")
  if not req_data["challenge"].get("secret"):
    raise ValueError("Missing '$.challenge.secret'")
  
  if not challenge_store.is_valid(req_data["challenge"].get("id"), req_data["challenge"].get("secret")):
    raise ValueError("Captcha challenge failed.")

  #defaults
  #--------
  if not req_data["app"]["owner"]["contact_person"].get("org_id"):
    req_data["app"]["owner"]["contact_person"]["org_id"] = req_data["app"]["owner"].get("org_id")
  if not req_data["app"]["owner"]["contact_person"].get("sub_org_id"):
    req_data["app"]["owner"]["contact_person"]["sub_org_id"] = req_data["app"]["owner"].get("sub_org_id")

  #validate field values
  #---------------------
  req_data["validated"] = {}
  owner_org = bcdc.get_organization(req_data["app"]["owner"].get("org_id"))
  if owner_org:
    req_data["validated"]["owner_org_name"] = owner_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.app.owner.org_id'")    
  
  owner_sub_org = bcdc.get_organization(req_data["app"]["owner"].get("sub_org_id"))
  if owner_sub_org:
    req_data["validated"]["owner_sub_org_name"] = owner_sub_org["title"]    
  
  owner_contact_org = bcdc.get_organization(req_data["app"]["owner"]["contact_person"].get("org_id"))
  if owner_contact_org:
    req_data["validated"]["owner_contact_org_name"] = owner_contact_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.app.owner.contact_person.org_id'")

  owner_contact_sub_org = bcdc.get_organization(req_data["app"]["owner"]["contact_person"].get("sub_org_id"))
  if owner_contact_sub_org:
    req_data["validated"]["owner_contact_sub_org_name"] = owner_contact_sub_org["title"]

  submitted_by_person_org = bcdc.get_organization(req_data["submitted_by_person"].get("org_id"))
  if submitted_by_person_org:
    req_data["validated"]["submitted_by_person_org_name"] = submitted_by_person_org["title"]

  submitted_by_person_sub_org = bcdc.get_organization(req_data["submitted_by_person"].get("sub_org_id"))
  if submitted_by_person_sub_org:
    req_data["validated"]["submitted_by_person_sub_org_name"] = submitted_by_person_sub_org["title"]

  if not submitted_by_person_org:
    req_data["validated"]["submitted_by_person_org_name"] = req_data["submitted_by_person"].get("org_name")

  #add a "status" attribute to track progress of the the request
  #-------------------------------------------------------------

  if not STATUS_KEY in req_data:
    req_data[STATUS_KEY] = {
      "state": PROCESSING_STATES["AWAITING_VERIFICATION"]
    }

  return req_data

def create_package(req_data):
  """
  Registers a new package with BCDC
  :param req_data: the req_data of the http request to the /register resource
  """
  package_dict = {
    "title": req_data["app"].get("title"),
    "name": bcdc.prepare_package_name(req_data["app"].get("title")),
    "org": settings.BCDC_PACKAGE_OWNER_ORG_ID,
    "sub_org": settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID,
    "owner_org": settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID,
    "notes": req_data["app"].get("description"),
    "groups": [{"id" : settings.BCDC_GROUP_ID}],
    "state": "active",
    "resource_status": req_data["app"].get("status", "completed"),
    "type": "WebService",
    "tag_string": "API",
    "tags": [{"name": "TODO"}],
    "sector": "Service",
    "edc_state": "DRAFT",
    "download_audience": req_data["app"]["security"].get("download_audience"),
    "view_audience":  req_data["app"]["security"].get("view_audience"),
    "metadata_visibility": req_data["app"]["security"].get("metadata_visibility"),
    "security_class": req_data["app"]["security"].get("security_class"),
    "license_id": req_data["app"]["license"].get("license_id"),
    "contacts": [
      {
        "name": req_data["app"]["owner"]["contact_person"].get("name"),
        "organization": req_data["app"]["owner"]["contact_person"].get("org_id", settings.BCDC_PACKAGE_OWNER_ORG_ID),
        "branch": req_data["app"]["owner"]["contact_person"].get("sub_org_id", settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID),
        "email": req_data["app"]["owner"]["contact_person"].get("business_email"),
        "role": req_data["app"]["owner"]["contact_person"].get("role", "pointOfContact"),
        "private": req_data["app"]["owner"]["contact_person"].get("private", "Display")
      }
    ]
  }

  try:
    package = bcdc.package_create(package_dict, api_key=settings.BCDC_API_KEY)
    app.logger.debug("Created metadata record: {}".format(bcdc.package_id_to_web_url(package["id"])))
    return package
  except (ValueError, RuntimeError) as e: 
    raise e

def create_app_resource(package_id, req_data):
  """
  Adds a new resource to the given package.  The new resource represents the URL of the app.
  :param package_id: the id of the package to add the resource to.
  :param req_data: the req_data of the request to /register as a dictionary
  :return: the new resource
  """
  
  #download api base url and check its content type (so we can create a 'resource' 
  #with the appropriate content type)
  format = "text"
  try:
    r = requests.get(req_data["app"]["url"])
    if r.status_code < 400:
      resource_content_type = r.headers['content-type']
      format = content_type_to_format(resource_content_type, "text")
  except requests.exceptions.ConnectionError as e:
    app.logger.warning("Unable to access app '{}' to determine content type.".format(req_data["app"]["url"]))
    pass

  #add the "API root" resource to the package
  resource_dict = {
    "package_id": package_id, 
    "url": req_data["app"]["url"],
    "format": format, 
    "name": "Application home"
  }
  resource = bcdc.resource_create(resource_dict, api_key=settings.BCDC_API_KEY)
  return resource

def create_api_spec_resource(package_id, req_data):
  """
  Adds a new resource to the given package.  The new resource represents the API spec.
  This function fails does nothing and returns None if $.existing_api.openapi_spec_url is not
  present in req_data.
  :param package_id: the id of the package to add the resource to.
  :param req_data: the body of the request to /register as a dictionary
  :return: the new resource
  """

  if req_data["existing_api"].get("openapi_spec_url"):
    resource_dict = {
      "package_id": package_id, 
      "url": req_data["existing_api"]["openapi_spec_url"],
      "format": "openapi-json",
      "name": "API specification"
    }
    resource = resource_create(resource_dict, api_key=settings.BCDC_API_KEY)
    return resource

  return None

def send_verification_email_to_submitter(req_data, verification_code):
  """
  Sends an email with a link to verify the API key request.
  (Verifying the request will advance to the next step of processing.)
  """

  email_body = html.get_verification_email_body(req_data, verification_code)

  send_email(
    to=[req_data["submitted_by_person"]["business_email"]], \
    bcc=None, \
    email_subject="Verify API Key Request - {}".format(req_data["api"]["title"]), \
    email_body=email_body,\
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent verification email to: {}.".format(req_data["submitted_by_person"]["business_email"]))


def send_notification_email_to_submitter(req_data):
  """
  Sends a notification email
  """
  to = [req_data["submitted_by_person"]["business_email"]]

  send_email(
    to=to, \
    email_subject="API Key Request - {}".format(req_data["api"]["title"]), \
    email_body=html.get_notification_email_body(req_data, include_new_metadata_url=False, include_msg=True), \
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent notification email to: {}.".format(to))

def send_notification_email_to_admin(req_data):
  """
  Sends a notification email
  """
  to = settings.TARGET_EMAIL_ADDRESSES.split(",")

  send_email(
    to=to, \
    email_subject="API Key Request - {}".format(req_data["api"]["title"]), \
    email_body=html.get_notification_email_body(req_data, include_new_metadata_url=True, include_msg=False), \
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent notification email to: {}. ".format(to))

def content_type_to_format(content_type, default=None):
  """
  Converts a content type (aka mine type, as would appear in the Content-Type header 
  of an HTTP request or response) into corresponding ckan resource string (html, json, xml, etc.)
  """
  if content_type.startswith("text/html"):
    return "html"
  if content_type.startswith("application/json"):
    return "json"
  if "xml" in content_type:
    return "xml"
  return default