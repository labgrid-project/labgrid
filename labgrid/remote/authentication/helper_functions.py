import datetime
import os
import jwt


def load_credential_from_file(filepath):
    '''
    Loads certificate from file and returns it as bytes

    Args:
        filepath (str): The path to the file to load

    Returns:
        The content of the certificate file as bytes
    '''
    real_path = os.path.join(os.path.dirname(__file__), filepath)
    with open(real_path, "rb") as f:
        return f.read()


token_secret = '3#pn$%agj02_r119*peydh&w+kt(2gy=n&e-68t19fup#33=)7'

# sample token details
jwt_token_details = {
  'id': 'labgrid',
  'username': 'labgrid-username',
  'firstName': 'firstName',
  'lastName': 'lastName',
  'email': 'labgrid-user@company.com',
  'isStaff': True,
  'exp': (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)),}


def generate_jwt_token(token_details=jwt_token_details, secret=token_secret):
    '''
    Generates a JWT token with the given token details and secret and return it
    '''
    return jwt.encode(token_details, secret, algorithm='HS256')


def is_token_valid(token, secret_key=token_secret):
    '''
    Validates the given token using the secret key and returns True if the token is valid

    Args:
        token (str): The token to validate
        secret_key (str): The secret key to use for validation

    Returns:
        True if the token is valid, False otherwise
    '''
    try:
        decoded_token =jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return False
    except jwt.InvalidTokenError:
        return False

    if not 'id' in decoded_token:
        return False

    if not 'exp' in decoded_token:
        return False

    exp_date = datetime.datetime.fromtimestamp(decoded_token['exp'])
    curr_date = datetime.datetime.utcnow()

    if exp_date < curr_date:
        return False

    return True

SERVER_CERTIFICATE=load_credential_from_file('../Certificates/server.crt')
SERVER_CERTIFICATE_KEY=load_credential_from_file('../Certificates/server.key')
