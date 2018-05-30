from pprint import pprint
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession


class AuthenticatorSession(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        def authenticate(realm, authid, details):  # pylint: disable=unused-argument
            pprint(details)
            principal = {'role': 'public', 'extra': {}}
            return principal

        yield self.register(authenticate, 'org.labgrid.authenticate')
