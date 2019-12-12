from flask_redis import FlaskRedis
#from flask_redis import redis
import json
import uuid
import string
import random
from captcha.image import ImageCaptcha
from . import settings

#------------------------------------------------------------------------------
# Constants
#------------------------------------------------------------------------------

MIN_CAPTCHA_TEXT_SIZE = 5
MAX_CAPTCHA_TEXT_SIZE = 6

class ChallengeStore(object):
  """
  This class provides an interface to store and retrieve "challenges".  A challenge is a 
  public ID and a SECRET.  The public ID can be used to generate a captcha image.
  A user's response to a captcha image can be compared to the challenge SECRET to confirm the
  user is human.
  """
  
  def __init__(self, app, db_url=None, default_ttl_seconds=settings.SECONDS_PER_DAY):
    
    self.app = app
    self.db_url = db_url

    if db_url:
      app.config["REDIS_URL"] = db_url

    self._default_ttl_seconds = default_ttl_seconds
    self._store = FlaskRedis(app)
    self._imageCaptcha = ImageCaptcha()


  def new_challenge(self):
    #number of letters and digits in the captcha secret
    secret_length = random.randint(MIN_CAPTCHA_TEXT_SIZE, MAX_CAPTCHA_TEXT_SIZE)

    #random id
    challenge_id = str(uuid.uuid4())

    #random secret of the chosen length
    secret = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(secret_length))

    challenge = {
      "challenge_id": challenge_id,
      "secret": secret
    }

    #save challenge to store
    try:
      self._store.set(challenge_id, secret.encode('utf-8'), ex=self._default_ttl_seconds)
    except redis.exceptions.ConnectionError as e:
      self.app.logger.error("Unable to connect to Redis database: '{}'. {}".format(self.db_url, e))
      raise RuntimeError("Unable to connect to Redis database.")
    except redis.exceptions.ResponseError as e:
      self.app.logger.error("Unable to save challenge to Redis database: {}.".format(e))
      raise RuntimeError("Unable to save challenge.")

    return challenge

  def is_valid(self, challenge_id, secret_to_check):
    secret = None
    try:    
      secret = self._store.get(challenge_id).decode('utf-8')
    except redis.exceptions.ConnectionError as e:
      self.app.logger.error("Unable to connect to Redis database: '{}'.".format(self.db_url))
      raise RuntimeError("Unable to connect to Redis database")
    except redis.exceptions.ResponseError as e:
      self.app.logger.error("Unable to get challenge from Redis database: {}.".format(e))
      raise RuntimeError("Unable to get challenge.")

    if not settings.CHALLENGE_SECRETS_CASE_SENSITIVE:
      secret = secret.lower()
      secret_to_check = secret_to_check.lower()

    if secret == secret_to_check:
      return True
    return False

  def challenge_id_to_captcha(self, challenge_id):
    """
    Creates a new PNG image which shows the secret corresponding
    to the specified challenge_id
    Returns a ByteIO object with the image content
    """
    try:    
      secret = self._store.get(challenge_id).decode('utf-8')
    except redis.exceptions.ConnectionError as e:
      self.app.logger.error("Unable to connect to Redis database: '{}'.".format(self.db_url))
      raise RuntimeError("Unable to connect to Redis database")
    except redis.exceptions.ResponseError as e:
      self.app.logger.error("Unable to get challenge from Redis database: {}.".format(e))
      raise RuntimeError("Unable to get challenge.")

    if not secret:
      raise ValueError("No such challenge")

    image_bytes = self._imageCaptcha.generate(secret)
    return image_bytes
