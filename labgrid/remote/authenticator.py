import logging
from pprint import pprint
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession


class AuthenticatorSession(ApplicationSession):
    @inlineCallbacks
    def onJoin(self, details):
        def authenticate(realm, authid, details):  # pylint: disable=unused-argument
            logging.warning("%s still uses deprecated ticket authentication. Please update.", authid)
            pprint(details)
            principal = {'role': 'public', 'extra': {}}
            return principal

        import warnings
        warnings.warn("Ticket authentication is deprecated. Please switch to anonymous authentication once all your exporters/clients support it: .crossbar/config-anonymous.yaml",
                      DeprecationWarning)

        yield self.register(authenticate, 'org.labgrid.authenticate')
