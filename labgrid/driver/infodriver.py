import logging
import re

import attr

from ..factory import target_factory
from ..step import step
from ..protocol import InfoProtocol, CommandProtocol
from .common import Driver
from .exception import ExecutionError

@target_factory.reg_driver
@attr.s(cmp=False)
class InfoDriver(Driver, InfoProtocol):
    """
    InfoDriver implementing the InfoProtocol on top of CommandProtocol drivers
    """

    # TODO: rework CommandProtocol binding to select correct underlying driver
    # (No UBoot/BareboxDriver, SSH > Serial,…)
    bindings = {'command': CommandProtocol}

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.logger = logging.getLogger("{}".format(self))

    @Driver.check_active
    @step(args=['interface'])
    def get_ip(self, interface="eth0"):
        """Returns the IP of the supplied interface"""
        try:
            ip_string = self.command.run_check("ip -o -4 addr show")
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

        return None

    @Driver.check_active
    @step(args=['service'])
    def get_service_status(self, service):
        """Returns True if service is active, False in all other cases"""
        _, _, exitcode = self.command.run(
            "systemctl --quiet is-active {}".format(service)
        )
        return exitcode == 0

    @Driver.check_active
    @step(result=True)
    def get_hostname(self):
        try:
            hostname_string = self.command.run_check("hostname")
        except ExecutionError:
            self.logger.debug('Hostname unavailable')
            return None
        self.logger.debug('Hostname String: %s', hostname_string)
        return hostname_string[0]
