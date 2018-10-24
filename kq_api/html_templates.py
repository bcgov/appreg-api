from jinja2 import Template
from . import settings


# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------

STATUS_KEY = "kq_status"
CSS_FILENAME = "css/bootstrap.css"

# -----------------------------------------------------------------------------
# Verify API Key - Success
# -----------------------------------------------------------------------------

def get_verify_key_request_success(req_data):
  """
  Creates the body of the notification email
  :param req_data: a request data object
  """

  include_new_metadata_url = False
  request_summary = get_request_data_summary_html(req_data, include_new_metadata_url)

  with open(CSS_FILENAME, 'r') as css_file:
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

  <div class="alert alert-info" role="alert">The API key request has been submitted for review.  You may be contacted if there are any questions about the request.  It may take about a week to review and approve the request.  If the request is approved the new API key will be sent to you by email.</div><br/>

  {{request_summary}}

  </div>
  </body>
  </html>
  """
  )

  params = {
    "req_data": req_data,
    "request_summary": request_summary
  }
  html = template.render(params)
  return html


# -----------------------------------------------------------------------------
# Verify API Key - Errors
# -----------------------------------------------------------------------------

def _general_msg(msg, is_err=False):
  with open(CSS_FILENAME, 'r') as css_file:
    css=css_file.read() #.replace('\n', '')  

  alert_class = "alert-info"
  if is_err:
    alert_class = "alert-danger"

  html = """
  <html>
  <head>
  <style>
  {}
  </style>
  </head>
  <title>API Key Request</title>
  <body>
  <div class="container">
  <h2>API Key Request</h2>
  <div class="alert {}" role="alert">{}</div>
  </div>
  </body>
  </html>  
  """.format(css, alert_class, msg)
  return html

def get_err_verify_key_request_general():
  return _general_msg("A server error occurred.  Unable to verify the API key request.  Please try again later.", True)

def get_err_verify_key_request_invalid_code():
  return _general_msg("Verification code is not valid.", True)

def get_err_verify_key_request_store():
  return _general_msg("A server error occurred.  Unable to verify the API key request.  Please try again later.", True)

def get_err_verify_key_request_already_done():
  return _general_msg("Your API key request has already been verified and sent to the API owner for review.  The API owner will contact you.")

def get_err_create_metadata(exception):
  msg = "Unable to create metadata record in the BC Data Catalog."
  if exception:
    msg += " {}".format(exception)
  return _general_msg(msg, True)

# -----------------------------------------------------------------------------
# Notification emails
# -----------------------------------------------------------------------------

def get_verification_email_body(req_data, verification_code):
  """
  Creates the body of the verification email
  :param req_data: the body of the request to /register as a dictionary
  :param verification_code: the code that the user can submit to indicate that
    they verify the request
  """

  with open(CSS_FILENAME, 'r') as css_file:
    css=css_file.read() #.replace('\n', '')  

  request_summary = get_request_data_summary_html(req_data)

  verification_url = "{}/verify_key_request?verification_code={}".format(settings.KQ_API_URL, verification_code)
  verification_link = "<a href='{}'>{}</a>".format(verification_url, verification_url)

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

  <p>A request has been made for a new <strong>{{req_data["api"]["title"]}} API Key</strong>.  This email address was given as the contact email of the person who submitted the request. If you did not request an API key, please disregard this email.  Otherwise, please click the link below (or paste it into a web browser) to confirm that you are the person who requested the API key, and that the details of the request are correct.</p><br/>

  <p>{{verification_link}}</p><br/>

  {{request_summary}}

  </div>
  </body>
  </html>
  """
  )

  params = {
    "req_data": req_data,
    "verification_link": verification_link,
    "request_summary": request_summary
  }
  html = template.render(params)
  return html

def get_notification_email_body(req_data, include_new_metadata_url=False, include_msg=False):
  """
  Creates the body of the notification email
  :param req_data: a request data object
  """

  request_summary = get_request_data_summary_html(req_data, include_new_metadata_url)

  msg = ""
  if include_msg:
    msg = "<div class='alert alert-info' role='alert'>This request will be submitted to the API owner for review and approval.</div><br/>"

  with open(CSS_FILENAME, 'r') as css_file:
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

  {{msg}}

  {{request_summary}}

  </div>
  </body>
  </html>
  """
  )

  params = {
    "req_data": req_data,
    "request_summary": request_summary,
    "msg": msg
  }
  html = template.render(params)
  return html

# -----------------------------------------------------------------------------
# Summary of API key request
# -----------------------------------------------------------------------------

def get_request_data_summary_html(req_data, include_new_metadata_url=False):
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
        {% if req_data["app"]["metadata_url"] %}
        Metadata Record: <a href="{{req_data["app"]["metadata_url"]}}">{{req_data["app"]["metadata_url"]}}</a><br/>
        {% endif %}
        {% if include_new_metadata_url and req_data.get(STATUS_KEY) and req_data.get(STATUS_KEY).get("new_metadata_record") and req_data.get(STATUS_KEY).get("new_metadata_record").get("metadata_web_url") %}
        Metadata Record: <a href="{{req_data.get(STATUS_KEY).get("new_metadata_record").get("metadata_web_url")}}">{{req_data.get(STATUS_KEY).get("new_metadata_record").get("metadata_web_url")}}</a><br/>
        {% endif %}
      </td>
    </tr>
    <tr>
      <th>API owner</th>
      <td>
        Organization: 
          {% if req_data["validated"]["owner_sub_org_name"] %} {{req_data["validated"].get("owner_sub_org_name")}}, {% endif %}
          {{req_data["validated"]["owner_org_name"]}}
      </td>
    </tr>
    <tr>
      <th>API primary contact person</th>
      <td>
        {{req_data["app"]["owner"]["contact_person"]["name"]}}<br/>
        Organization:
          {% if req_data["validated"]["owner_contact_sub_org_name"] %} {{req_data["validated"].get("owner_contact_sub_org_name")}}, {% endif %}
          {{req_data["validated"]["owner_contact_org_name"]}}<br/>
        {{req_data["app"]["owner"]["contact_person"]["business_email"]}}<br/>
        {{req_data["app"]["owner"]["contact_person"]["business_phone"]}}<br/>
        Role: {{req_data["app"]["owner"]["contact_person"]["role"]}}
      </td>
    </tr>
    <tr>
      <th>Request submitted by</th>
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
    "STATUS_KEY": STATUS_KEY,
    "include_new_metadata_url": include_new_metadata_url
  }
  html = template.render(params)
  return html