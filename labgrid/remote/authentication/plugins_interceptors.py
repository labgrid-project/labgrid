import grpc
from .helper_functions import generate_jwt_token, is_token_valid


JWT_TOKEN = generate_jwt_token()

class CustomAuthMetadataPlugin(grpc.AuthMetadataPlugin):
  '''
  Authentication plugin used to add {'x-signature', JWT_TOKEN} HTTP header
  '''
  def __call__(self, context, callback):
    signature = context.method_name[::-1]
    signature = JWT_TOKEN
    callback((("x-signature", signature),), None)


class SignatureValidationInterceptor(grpc.aio.ServerInterceptor):
  '''
  Middleware used to validate the JWT token in the HTTP header
  '''
  def __init__(self):
    def abort(ignored_request, context):
      context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid signature")
      self._abort_handler = grpc.unary_unary_rpc_method_handler(abort)

  def intercept_service(self, continuation, handler_call_details):
    '''
    Extracts the token from the HTTP header and validates it
    '''
    token = ''

    for item in  handler_call_details.invocation_metadata:
      dictionary = item._asdict()
      if dictionary['key'] == 'x-signature':
        token = dictionary['value']
        break

    if token != '':
      if is_token_valid(token):
        return continuation(handler_call_details)

    self._abort_handler()
