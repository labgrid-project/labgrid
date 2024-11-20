import grpc

token_value = 'authorized'

class DefaultAuthMetadataPlugin(grpc.AuthMetadataPlugin):
  '''
  Authentication plugin used to add {'authorization', "Bearer <token_value>"} HTTP header
  '''
  def __call__(self, context, callback):
    callback((("authorization", "Bearer {}".format(token_value)),), None)


class DefaultServerInterceptor(grpc.aio.ServerInterceptor):
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
      if dictionary['key'] == 'authorization':
        token = dictionary['value']
        if "Bearer " in token:
          token = token.replace("Bearer ", "")
          break

    if token != '' and token == token_value:
      return continuation(handler_call_details)

    self._abort_handler()
