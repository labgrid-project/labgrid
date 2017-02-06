import re

from ..step import step

class InfoMixin:
    """
    InfoMixin implementing common functions for drivers which support the InfoProtocol
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @step(args=['interface'])
    def get_ip(self, interface="eth0"):
        """Returns the IP of the supplied interface"""
        if self._status == 1:
            try:
                ip_string = self.run_check("ip -o -4 addr show")
            except ExecutionError:
                self.logger.debug('No ip address found')
                return None

            regex = re.compile(
                r"""\d+:       # Match the leading number
                \s+(?P<if>\w+) # Match whitespace and interfacename
                \s+inet\s+(?P<ip>[\d.]+) # Match IP Adress
                /(?P<prefix>\d+) # Match prefix
                .*global # Match global scope, not host scope""", re.X
            )
            self.logger.debug('IP String: %s', ip_string)
            result = {}
            for line in ip_string:
                match = regex.match(line)
                if match:
                    match = match.groupdict()
                    self.logger.debug("Match dict: %s", match)
                    result[match['if']] = match['ip']
            self.logger.debug("Complete result: %s", result)
            if result:
                return result[interface]
            else:
                return None

    @step(args=['service'])
    def get_service_status(self, service):
        """Returns True if service is active, False in all other cases"""
        if self._status == 1:
            _, _, exitcode = self.run(
                "systemctl --quiet is-active {}".format(service)
            )
            return exitcode == 0

    @step(result=True)
    def get_hostname(self):
        if self._status == 1:
            try:
                hostname_string = self.run_check("hostname")
            except ExecutionError:
                self.logger.debug('Hostname unavailable')
                return None
            self.logger.debug('Hostname String: %s', hostname_string)
            return hostname_string[0]
