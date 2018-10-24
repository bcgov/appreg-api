from flask_redis import FlaskRedis
from flask_redis import redis
import uuid
import json

SECONDS_PER_DAY = 86400

class RequestStore(object):
  """
  This class provides an interface to persist API key requests.  Each persisted request
  is assigned a "verification code" which can be used later to access or remove the request.
  """
  
  def __init__(self, app, db_url=None, default_ttl_seconds=SECONDS_PER_DAY):
    
    self.app = app
    self.db_url = db_url

    if db_url:
      app.config["REDIS_URL"] = db_url

    self._default_ttl_seconds = default_ttl_seconds
    self._store = FlaskRedis(app)

  def save_request(self, req_data, verification_code=None, ttl_seconds=None):
    """
    Saves the given API request object to permenant storage.  A new, unique "verification code" 
    is assigned to the request.  The verification code is returned.
    """
    if not verification_code:
      verification_code = uuid.uuid4()
    if not ttl_seconds:
      ttl_seconds = self._default_ttl_seconds
    try:
      #serialize as json then save
      req_data_as_json = json.dumps(req_data)
      self._store.set(verification_code, req_data_as_json, ex=ttl_seconds)
    except redis.exceptions.ConnectionError as e:
      self.app.logger.error("Unable to connect to Redis database: '{}'.".format(self.db_url))
      raise RuntimeError("Unable to connect to Redis database.")
    return verification_code

  def load_request(self, verification_code):
    """
    If the verification_code exists, eturns the corresponding request data 
    (req_data) object. Otherwise returns None.
    """
    req_data = None
    try:
      #get from redis, then deserialize the json
      req_data_as_json = self._store.get(verification_code)
      if req_data_as_json:
        req_data = json.loads(req_data_as_json)
    except redis.exceptions.ConnectionError as e:
      self.app.logger.error("Unable to connect to Redis database: '{}'.".format(self.db_url))
      raise RuntimeError("Unable to connect to Redis database")
    return req_data
