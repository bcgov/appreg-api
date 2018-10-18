from flask import Flask, Response, jsonify, request, redirect, url_for, g
from jinja2 import Template
from . import settings
from .bcdc import package_id_to_web_url, package_id_to_api_url, prepare_package_name, package_create, resource_create, get_organization
from .emailer import send_email
import os
import json
import uuid
import requests
import logging
from flask_cors import CORS

app = Flask(__name__)

#In debug mode add CORS headers to responses. (When not in debug mode, it is 
#assumed that CORS headers will be controlled externally, such as by a reverse
#proxy)
if "FLASK_DEBUG" in os.environ and os.environ["FLASK_DEBUG"]:
  CORS(app)

#setup logging
app.logger.setLevel(getattr(logging, settings.LOG_LEVEL)) #main logger's level

#inject some initial log messages
app.logger.info("Initializing {}".format(__name__))
app.logger.info("Log level is '{}'".format(settings.LOG_LEVEL))
 

#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

API_SPEC_FILENAME = os.path.join(app.root_path, "../docs/kq-api.openapi3.json")

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

  #get request req_data
  try:
    req_data = request.get_json()
  except Error as e:
    return jsonify({"msg": "content req_data is not valid json"}), 400

  try:
    req_data = clean_and_validate_req_data(req_data)
  except ValueError as e:
    return jsonify({"msg": "{}".format(e)}), 400
  except RuntimeError as e:
    app.logger.error("{}".format(e));
    return jsonify({"msg": "An unexpected error occurred while validating the API key request."}), 500

  success_resp = {}
  
  try:
    check_bad_language(req_data["title"])
  except ValueError as e:
    return jsonify({"msg": "Inappropriate language found in the application's title.  {}".format(e)}), 400

  try:
    check_bad_language(req_data["description"])
  except ValueError as e:
    return jsonify({"msg": "Inappropriate language found in the application's description.  {}".format(e)}), 400

  try:
    verification_code = save_api_key_request(req_data)
  except RuntimeError as e:
    app.logger.error("Unable to save request. {}".format(e))
    return jsonify({"msg": "Server error.  Unable to register API key request."}), 500

  try:
    send_verification_email(req_data, verification_code)
  except Exception as e: 
    app.logger.error("Unable to send verification email for new API. {}".format(e))
    return jsonify({"msg": "Server error.  Unable to register API key request."}), 500

  return jsonify(success_resp), 200

@app.route('/verify_key_request', methods=["GET"])
def verify_key_request():
  app.logger.info("verify_key_request message received")
  verification_code = request.args.get('verification_code')
  
  req_data = load_api_key_request(verification_code)
  if not req_data:
    err_html = "Verification code is not valid."
    return err_html, 404

  metadata_web_url = None
  #create a draft metadata record (if one doesn't exist yet)
  if not req_data.get("metadata_url"):
    package = None
    try:
      package = create_package(req_data)
      if not package:
        raise ValueError("Unknown reason")
      #add info about the new metadata record to the response
      metadata_web_url = package_id_to_web_url(package["id"])
      metadata_api_url = package_id_to_api_url(package["id"])
      success_resp["new_metadata_record"] = {
        "id": package["id"],
        "web_url": metadata_web_url,
        "api_url": metadata_api_url
      }
    except ValueError as e: #user input errors cause HTTP 400
      return jsonify({"msg": "Unable to create metadata record in the BC Data Catalog. {}".format(e)}), 400
    except RuntimeError as e: #unexpected system errors cause HTTP 500
      app.logger.error("Unable to create metadata record in the BC Data Catalog. {}".format(e))
      return jsonify({"msg": "Unable to create metadata record in the BC Data Catalog."}), 500

    try:
      create_app_resource(package["id"], req_data)
    except ValueError as e: #perhaps other errors are possible too??  if so, catch those too
      app.logger.warn("Unable to create app root resource associated with the new metadata record. {}".format(e))
  
  #there is an existing metadata record
  else:
    package_id = "TODO: lookup from existing metadata record"

  send_notification_email(req_data, package_id)

  success_html "The API key request has been submitted.  You will be contacted when the key is ready.  It may take about a week to generate the key.  Todo: show API key request summary here."
  return success_html, 200

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def save_api_key_request(req_data):
  """
  Saves the given API request object to permenant storage.  A new, unique "verification code" 
  is assigned to the request.  The verification code is returned.
  """
  new_verification_code = uuid.uuid4()
  app.logger.warn("TODO: save request")
  return new_verification_code

def load_api_key_request(verification_code):
  """
  If the verification_code exists, eturns the corresponding request data 
  (req_data) object. Otherwise returns None.
  """
  app.logger.warn("TODO: load request data")
  req_data = None
  return req_data

def delete_api_key_request(verification_code):
  app.logger.warn("TODO: delete verification code")

def check_bad_language(str):
  """
  Checks the given string for inappropriate language (e.g. swear words).
  raises a ValueError on any problem.  Otherwise return None to indicate no problems
  """
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
  if not req_data["app"]["owner"]["app"].get("business_email"):
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


  #defaults
  #--------
  if not req_data["app"]["owner"]["contact_person"].get("org_id"):
    req_data["app"]["owner"]["contact_person"]["org_id"] = req_data["app"]["owner"].get("org_id")
  if not req_data["app"]["owner"]["contact_person"].get("sub_org_id"):
    req_data["app"]["owner"]["contact_person"]["sub_org_id"] = req_data["app"]["owner"].get("sub_org_id")

  #validate field values
  #---------------------
  req_data["validated"] = {}
  owner_org = get_organization(req_data["app"]["owner"].get("org_id"))
  if owner_org:
    req_data["validated"]["owner_org_name"] = owner_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.app.owner.org_id'")    
  
  owner_sub_org = get_organization(req_data["app"]["owner"].get("sub_org_id"))
  if owner_sub_org:
    req_data["validated"]["owner_sub_org_name"] = owner_sub_org["title"]    
  
  owner_contact_org = get_organization(req_data["app"]["owner"]["contact_person"].get("org_id"))
  if owner_contact_org:
    req_data["validated"]["owner_contact_org_name"] = owner_contact_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.app.owner.contact_person.org_id'")

  owner_contact_sub_org = get_organization(req_data["app"]["owner"]["contact_person"].get("sub_org_id"))
  if owner_contact_sub_org:
    req_data["validated"]["owner_contact_sub_org_name"] = owner_contact_sub_org["title"]

  submitted_by_person_org = get_organization(req_data["submitted_by_person"].get("org_id"))
  if submitted_by_person_org:
    req_data["validated"]["submitted_by_person_org_name"] = submitted_by_person_org["title"]

  submitted_by_person_sub_org = get_organization(req_data["submitted_by_person"].get("sub_org_id"))
  if submitted_by_person_sub_org:
    req_data["validated"]["submitted_by_person_sub_org_name"] = submitted_by_person_sub_org["title"]

  if not submitted_by_person_org:
    req_data["validated"]["submitted_by_person_org_name"] = req_data["submitted_by_person"].get("org_name")

  return req_data

def create_package(req_data):
  """
  Registers a new package with BCDC
  :param req_data: the req_data of the http request to the /register resource
  """
  package_dict = {
    "title": req_data["app"].get("title"),
    "name": prepare_package_name(req_data["app"].get("title")),
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
    package = package_create(package_dict, api_key=settings.BCDC_API_KEY)
    app.logger.debug("Created metadata record: {}".format(package_id_to_web_url(package["id"])))
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
  resource = resource_create(resource_dict, api_key=settings.BCDC_API_KEY)
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

def send_verification_email(req_data, verification_code):
  """
  Sends an email with a link to verify the API key request.
  (Verifying the request will advance to the next step of processing.)
  """

  email_body = prepare_verification_email_body(req_data, verification_code)

  send_email(
    req_data["submitted_by_person"]["business_email"], \
    email_subject="Verify API Key Request - {}".format(req_data["api"]["title"]), \
    email_body=email_body\
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent verification email to: {}".format(settings.TARGET_EMAIL_ADDRESSES))


def send_notification_email(req_data, package_id):
  """
  Sends a notification email
  """

  send_email(
    settings.TARGET_EMAIL_ADDRESSES, \
    email_subject="API Key Request - {}".format(req_data["metadata_details"]["title"]), \
    email_body=prepare_notification_email_body(req_data, package_id), \
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent notification email to: {}".format(settings.TARGET_EMAIL_ADDRESSES))


def prepare_verification_email_body(req_data, verification_code):
  """
  Creates the body of the verification email
  :param req_data: the body of the request to /register as a dictionary
  :param verification_code: the code that the user can submit to indicate that
    they verify the request
  """

  css_filename = "css/bootstrap.css"

  owner_org = get_organization(req_data["metadata_details"]["owner"]["org_id"])

  with open(css_filename, 'r') as css_file:
    css=css_file.read() #.replace('\n', '')  

  request_summary = prepare_request_data_summary_html(req_data)
  verification_link = "<a href='http://url_here'>http://url_here</a>

  template = Template("""
  <html>
  <head>
  <style>
  """
  +css+
  """
  .table-condensed {font-size: 12px;}
  </style>
  </head>
  <title>Verify API Key Request - {{req_data["api"]["title"]}}</title>
  <body>
  <div class="container">
  <h2>API Key Request - {{req_data["api"]["title"]}}</h2>

  <p>A request has been made for a new <strong>{{req_data["api"]["title"]}} API Key</strong>.  This email address was given as the contact email of the person who submitted the request. If you did not request an API key, please disregard this email.  Otherwise, please click the link below (or paste it into a web browser) to confirm that you are the person who requested the API key, and that the details of the request are correct.

  {{verification_link}}

  {{request_summary}}

  </div>
  </body>
  </html>
  """
  )

  params = {
    "req_data": req_data,
    "metadata": {
      "web_url": metadata_web_url
    }
  }
  html = template.render(params)
  return html

def prepare_notification_email_body(req_data, metadata_web_url):
  """
  Creates the body of the notification email
  :param req_data: the body of the request to /register as a dictionary
  :param metadata_web_url: a BCDC metadata record url
  """

  css_filename = "css/bootstrap.css"

  request_summary = prepare_request_data_summary_html(req_data)

  with open(css_filename, 'r') as css_file:
    css=css_file.read() #.replace('\n', '')  

  template = Template("""
  <html>
  <head>
  <style>
  """
  +css+
  """
  .table-condensed {font-size: 12px;}
  </style>
  </head>
  <title>API Key Request - {{req_data["api"]["title"]}}</title>
  <body>
  <div class="container">
  <h2>API Key Request - {{req_data["api"]["title"]}}</h2>

  <p>A request for an API key has been made.  The details follow:</p>

  {{request_summary}}

  </div>
  </body>
  </html>
  """
  )

  params = {
    "req_data": req_data,
    "metadata": {
      "web_url": metadata_web_url
    }
  }
  html = template.render(params)
  return html

def prepare_request_data_summary_html(req_data):
  owner_org = get_organization(req_data["metadata_details"]["owner"]["org_id"])
  template = Template("""
  <table class="table table-condensed">
    <tr>
      <th>API for which a key is requested</th>
      <td>{{req_data["api"]["title"]}}</td>
    </tr>
    <tr>
      <th>Application that will use the API key</th>
      <td>
        Title: {{req_data["app"]["title"]}}<br/>
        Description: {{req_data["app"]["description"]}}<br/>
        URL: {{req_data["app"]["url"]}}<br/>
        Metadata Record: <a href="{{req_data["app"]["metadata_url"]}}">{{req_data["app"]["metadata_url"]}}</a><br/>
      </td>
    </tr>
    <tr>
      <th>API Owner</th>
      <td>
        Organization: 
          {% if req_data["validated"]["owner_sub_org_name"] %} {{req_data["validated"].get("owner_sub_org_name")}}, {% endif %}
          {{req_data["validated"]["owner_org_name"]}}
      </td>
    </tr>
    <tr>
      <th>API Primary Contact Person</th>
      <td>
        {{req_data["metadata_details"]["owner"]["contact_person"]["name"]}}<br/>
        Organization:
          {% if req_data["validated"]["owner_contact_sub_org_name"] %} {{req_data["validated"].get("owner_contact_sub_org_name")}}, {% endif %}
          {{req_data["validated"]["owner_contact_org_name"]}}<br/>
        {{req_data["metadata_details"]["owner"]["contact_person"]["business_email"]}}<br/>
        {{req_data["metadata_details"]["owner"]["contact_person"]["business_phone"]}}<br/>
        Role: {{req_data["metadata_details"]["owner"]["contact_person"]["role"]}}
      </td>
    </tr>
    <tr>
      <th>Submitted by</th>
      <td>
        {{req_data["submitted_by_person"]["name"]}}<br/>
        Organization:
          {% if req_data["validated"]["submitted_by_person_sub_org_name"] %} {{req_data["validated"].get("submitted_by_person_sub_org_name")}}, {% endif %}
          {{req_data["validated"]["submitted_by_person_org_name"]}}<br/>
        {{req_data["submitted_by_person"]["business_email"]}}<br/>
        {{req_data["submitted_by_person"]["business_phone"]}}<br/>
        Role: {{req_data["submitted_by_person"]["role"]}}
      </td>
    </tr>
  </table>
  """
  )

  params = {
    "req_data": req_data,
  }
  html = template.render(params)
  return html

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