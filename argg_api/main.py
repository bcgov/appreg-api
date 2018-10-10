from flask import Flask, Response, jsonify, request, redirect, url_for, g
from jinja2 import Template
from . import settings
from .bcdc import package_id_to_web_url, package_id_to_api_url, prepare_package_name, package_create, resource_create, get_organization
from .emailer import send_email
import os
import json
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

API_SPEC_FILENAME = os.path.join(app.root_path, "../docs/argg-api.openapi3.json")

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

@app.route('/register', methods=["POST"])
def register():
  """
  Post a new API to be registered
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
    return jsonify({"msg": "An unexpected error occurred while validating the API registration request."}), 500

  success_resp = {}
  metadata_web_url = None

  #create a draft metadata record (if one doesn't exist yet)
  if not req_data.get("existing_metadata_url"):
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
      create_api_root_resource(package["id"], req_data)
    except ValueError as e: #perhaps other errors are possible too??  if so, catch those too
      app.logger.warn("Unable to create API root resource associated with the new metadata record. {}".format(e))
  
    try:
      create_api_spec_resource(package["id"], req_data)
    except ValueError as e: #perhaps other errors are possible too??  if so, catch those too
      app.logger.warn("Unable to create API spec resource associated with the new metadata record. {}".format(e))

  #there is an existing metadata record
  else:
    metadata_web_url = req_data.get("existing_metadata_url")

  try:
    send_notification_email(req_data, metadata_web_url)
  except Exception as e: 
    app.logger.error("Unable to send notification email for new API. {}".format(e))

  return jsonify(success_resp), 200

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

def clean_and_validate_req_data(req_data):

  #ensure req_data folder hierarchy exists
  #---------------------------------------
  if not req_data:
    req_data = {}
  if not req_data.get("submitted_by_person"):
    req_data["submitted_by_person"] = {}
  if not req_data.get("metadata_details"):
    req_data["metadata_details"] = {}
  if not req_data["metadata_details"].get("owner"):
    req_data["metadata_details"]["owner"] = {}
  if not req_data["metadata_details"]["owner"].get("contact_person"):
    req_data["metadata_details"]["owner"]["contact_person"] = {}
  if not req_data["metadata_details"].get("security"):
    req_data["metadata_details"]["security"] = {}
  if not req_data["metadata_details"].get("license"):
    req_data["metadata_details"]["license"] = {}
  if not req_data.get("existing_api"):
    req_data["existing_api"] = {}
  if not req_data.get("gateway"):
    req_data["gateway"] = {}

  #check that required fields are present
  #--------------------------------------
  if not req_data["metadata_details"].get("title"):
    raise ValueError("Missing '$.metadata_details.title'")
  if not req_data["metadata_details"].get("description"):
    raise ValueError("Missing '$.metadata_details.description'")

  if not req_data["metadata_details"]["owner"].get("org_id"):
    raise ValueError("Missing '$.metadata_details.owner.org_id'")
  
  if not req_data["metadata_details"]["owner"]["contact_person"].get("name"):
    raise ValueError("Missing '$.metadata_details.owner.contact_person.name'")
  if not req_data["metadata_details"]["owner"]["contact_person"].get("business_email"):
    raise ValueError("Missing '$.metadata_details.owner.contact_person.business_email'") 

  if not req_data["metadata_details"]["security"].get("download_audience"):
    raise ValueError("Missing '$.metadata_details.security.download_audience'")
  if not req_data["metadata_details"]["security"].get("view_audience"):
    raise ValueError("Missing '$.metadata_details.security.view_audience'")
  if not req_data["metadata_details"]["security"].get("metadata_visibility"):
    raise ValueError("Missing '$.metadata_details.security.metadata_visibility'")
  if not req_data["metadata_details"]["security"].get("security_class"):
    raise ValueError("Missing '$.metadata_details.security.security_class'")

  if not req_data["metadata_details"]["license"].get("license_id"):
    raise ValueError("Missing '$.metadata_details.license.license_id'")

  if not req_data["submitted_by_person"].get("name"):
    raise ValueError("Missing '$.submitted_by_person.name'")
  if not req_data["submitted_by_person"].get("org_id") and not req_data["submitted_by_person"].get("org_name"):
    raise ValueError("Missing one of '$.submitted_by_person.org_id' or '$submitted_by_person.org_name'")
  if not req_data["submitted_by_person"].get("business_email"):
    raise ValueError("Missing '$.submitted_by_person.business_email'")

  if not req_data["existing_api"].get("base_url"):
    raise ValueError("Missing '$.existing_api.base_url'")

#  if not req_data["gateway"].get("use_gateway"):
#    raise ValueError("Missing '$.gateway.use_gateway'")

  #clean fields
  #------------
  #change Title to title-case.  This can be problematic for abbreviations, such as "BC" (which becomes "Bc")
  #req_data["metadata_details"]["title"] = req_data["metadata_details"]["title"].title()

  #defaults
  #--------
  if not req_data["metadata_details"]["owner"]["contact_person"].get("org_id"):
    req_data["metadata_details"]["owner"]["contact_person"]["org_id"] = req_data["metadata_details"]["owner"].get("org_id")
  if not req_data["metadata_details"]["owner"]["contact_person"].get("sub_org_id"):
    req_data["metadata_details"]["owner"]["contact_person"]["sub_org_id"] = req_data["metadata_details"]["owner"].get("sub_org_id")

  #validate field values
  #---------------------
  req_data["validated"] = {}
  owner_org = get_organization(req_data["metadata_details"]["owner"].get("org_id"))
  if owner_org:
    req_data["validated"]["owner_org_name"] = owner_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.metadata_details.owner.org_id'")    
  
  owner_sub_org = get_organization(req_data["metadata_details"]["owner"].get("sub_org_id"))
  if owner_sub_org:
    req_data["validated"]["owner_sub_org_name"] = owner_sub_org["title"]    
  
  owner_contact_org = get_organization(req_data["metadata_details"]["owner"]["contact_person"].get("org_id"))
  if owner_contact_org:
    req_data["validated"]["owner_contact_org_name"] = owner_contact_org["title"]
  else:
    raise ValueError("Unknown organization specified in '$.metadata_details.owner.contact_person.org_id'")

  owner_contact_sub_org = get_organization(req_data["metadata_details"]["owner"]["contact_person"].get("sub_org_id"))
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
    "title": req_data["metadata_details"].get("title"),
    "name": prepare_package_name(req_data["metadata_details"].get("title")),
    "org": settings.BCDC_PACKAGE_OWNER_ORG_ID,
    "sub_org": settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID,
    "owner_org": settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID,
    "notes": req_data["metadata_details"].get("description"),
    "groups": [{"id" : settings.BCDC_GROUP_ID}],
    "state": "active",
    "resource_status": req_data["metadata_details"].get("status", "completed"),
    "type": "WebService",
    "tag_string": "API",
    "tags": [{"name": "API"}],
    "sector": "Service",
    "edc_state": "DRAFT",
    "download_audience": req_data["metadata_details"]["security"].get("download_audience"),
    "view_audience":  req_data["metadata_details"]["security"].get("view_audience"),
    "metadata_visibility": req_data["metadata_details"]["security"].get("metadata_visibility"),
    "security_class": req_data["metadata_details"]["security"].get("security_class"),
    "license_id": req_data["metadata_details"]["license"].get("license_id"),
#    "license_title": req_data["metadata_details"]["license"].get("license_title"), #auto added if license_id is specified
#    "license_url": "http://www2.gov.bc.ca/gov/content/home/copyright", #auto added if license_id is specified
    "contacts": [
      {
        "name": req_data["metadata_details"]["owner"]["contact_person"].get("name"),
        "organization": req_data["metadata_details"]["owner"]["contact_person"].get("org_id", settings.BCDC_PACKAGE_OWNER_ORG_ID),
        "branch": req_data["metadata_details"]["owner"]["contact_person"].get("sub_org_id", settings.BCDC_PACKAGE_OWNER_SUB_ORG_ID),
        "email": req_data["metadata_details"]["owner"]["contact_person"].get("business_email"),
        "role": req_data["metadata_details"]["owner"]["contact_person"].get("role", "pointOfContact"),
        "private": req_data["metadata_details"]["owner"]["contact_person"].get("private", "Display")
      }
    ]
  }

  try:
    package = package_create(package_dict, api_key=settings.BCDC_API_KEY)
    app.logger.debug("Created metadata record: {}".format(package_id_to_web_url(package["id"])))
    return package
  except (ValueError, RuntimeError) as e: 
    raise e

def create_api_root_resource(package_id, req_data):
  """
  Adds a new resource to the given package.  The new resource represents the base URL of the API.
  :param package_id: the id of the package to add the resource to.
  :param req_data: the req_data of the request to /register as a dictionary
  :return: the new resource
  """
  
  #download api base url and check its content type (so we can create a 'resource' 
  #with the appropriate content type)
  format = "text"
  try:
    r = requests.get(req_data["existing_api"]["base_url"])
    if r.status_code < 400:
      resource_content_type = r.headers['content-type']
      format = content_type_to_format(resource_content_type, "text")
  except requests.exceptions.ConnectionError as e:
    app.logger.warning("Unable to access API '{}' to determine content type.".format(req_data["existing_api"]["base_url"]))
    pass

  #add the "API root" resource to the package
  resource_dict = {
    "package_id": package_id, 
    "url": req_data["existing_api"]["base_url"],
    "format": format, 
    "name": "API root"
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

def send_notification_email(req_data, package_id):
  """
  Sends a notification email
  """

  send_email(
    settings.TARGET_EMAIL_ADDRESSES, \
    email_subject="New API Registered - {}".format(req_data["metadata_details"]["title"]), \
    email_body=prepare_email_body(req_data, package_id), \
    smtp_server=settings.SMTP_SERVER, \
    smtp_port=settings.SMTP_PORT, \
    from_email_address=settings.FROM_EMAIL_ADDRESS, \
    from_password=settings.FROM_EMAIL_PASSWORD)
  app.logger.debug("Sent notification email to: {}".format(settings.TARGET_EMAIL_ADDRESSES))


def prepare_email_body(req_data, metadata_web_url):
  """
  Creates the body of the notification email
  :param req_data: the body of the request to /register as a dictionary
  :param metadata_web_url: a BCDC metadata record url
  """

  css_filename = "css/bootstrap.css"

  owner_org = get_organization(req_data["metadata_details"]["owner"]["org_id"])

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
  <title>A new API has been registered</title>
  <body>
  <div class="container">
  <h2>A new API has been registered</h2>

  <table class="table table-condensed">
    <tr>
      <th>Title</th>
      <td>{{req_data["metadata_details"]["title"]}}</td>
    </tr>
    <tr>
      <th>Description</th>
      <td>{{req_data["metadata_details"]["description"]}}</td>
    </tr>
    <tr>
      <th>Metadata record</th>
      <td><a href="{{metadata["web_url"]}}">{{metadata["web_url"]}}</a></td>
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
    <tr>
      <th>API</th>
      <td>
        <a href="{{req_data["existing_api"]["base_url"]}}">{{req_data["existing_api"]["base_url"]}}</a><br/>
        Supports
          CORS: {% if req_data["existing_api"]["supports"].get("cors") %} {{req_data["existing_api"]["supports"].get("cors")}} {% else %} unknown {% endif %}, 
          HTTPS: {% if req_data["existing_api"]["supports"].get("https") %} {{req_data["existing_api"]["supports"].get("https")}} {% else %} unknown {% endif %} 
      </td>
    </tr>
    <tr>
      <th>OpenAPI specification</th>
      <td>
        {% if req_data["existing_api"].get("openapi_spec_url") %}
          <a href='{{req_data["existing_api"].get("openapi_spec_url")}}'>{{req_data["existing_api"].get("openapi_spec_url")}}</a>
        {% else %}
          None
        {% endif %}
      </td>
    </tr>
    <tr>
      <th>API gateway?</th>
      <td>
        Use Gateway?:{% if req_data["gateway"].get("use_gateway") %} 
          Yes<br/>
          {% if req_data["gateway"].get("use_throttling") != None %} Enable throttling?: {{req_data["gateway"].get("use_throttling")}} {% endif %}<br/>
          {% if req_data["gateway"].get("restrict_access") != None %} Use API keys?: {{req_data["gateway"].get("restrict_access")}} {% endif %}<br/>
          Suggested API short name?: {{req_data["gateway"].get("api_shortname", "not specified")}}
        {% else %} 
          No 
        {% endif %}

      </td>
    </tr>
  </table>

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