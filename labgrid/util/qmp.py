import json
import logging
import attr


@attr.s(cmp=False)
class QMPMonitor:
    monitor_out = attr.ib()
    monitor_in = attr.ib()

    def __attrs_post_init__(self):
        self.logger = logging.getLogger("{}:".format(self))
        self._negotiate_capabilities()

    def _negotiate_capabilities(self):
        greeting = self._read_parse_json()
        if not greeting.get('QMP'):
            raise IOError

        self.monitor_in.write(json.dumps({"execute": "qmp_capabilities"}).encode("utf-8"))
        self.monitor_in.write("\n".encode("utf-8"))
        self.monitor_in.flush()

        answer = self._read_parse_json()
        if not "return" in answer:
            raise QMPError("Could not connect to QMP: {0}".format(answer))

    def _read_parse_json(self):
        line = self.monitor_out.readline().decode('utf-8')
        self.logger.debug("Received line: %s", line)
        return json.loads(line)

    def execute(self, command):
        json_command = {"execute": command}

        self.monitor_in.write(json.dumps(json_command).encode("utf-8"))
        self.monitor_in.write("\n".encode("utf-8"))
        self.monitor_in.flush()

        answer = self._read_parse_json()
        # skip all asynchronous events
        while answer.get('event'):
            answer = self._read_parse_json()
        if "error" in answer:
            raise QMPError(answer['error'])
        return answer

@attr.s(cmp=False)
class QMPError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
