import json
import logging
import attr


@attr.s(eq=False)
class QMPMonitor:
    monitor_out = attr.ib()
    monitor_in = attr.ib()

    def __attrs_post_init__(self):
        self.logger = logging.getLogger(f"{self}")
        self._negotiate_capabilities()

    def _negotiate_capabilities(self):
        greeting = self._read_parse_json()
        if not greeting.get('QMP'):
            raise QMPError("QMP greeting message invalid")

        self.monitor_in.write(json.dumps({"execute": "qmp_capabilities"}).encode("utf-8"))
        self.monitor_in.write("\n".encode("utf-8"))
        self.monitor_in.flush()

        answer = self._read_parse_json()
        if not "return" in answer:
            raise QMPError(f"Could not connect to QMP: {answer}")

    def _read_parse_json(self):
        line = self.monitor_out.readline().decode('utf-8')
        self.logger.debug("Received line: %s", line.rstrip("\r\n"))
        if not line:
            raise QMPError("Received empty response")
        return json.loads(line)

    def execute(self, command, arguments={}):
        json_command = {"execute": command, "arguments": arguments}

        self.monitor_in.write(json.dumps(json_command).encode("utf-8"))
        self.monitor_in.write("\n".encode("utf-8"))
        self.monitor_in.flush()

        answer = self._read_parse_json()
        # skip all asynchronous events
        while answer.get('event'):
            answer = self._read_parse_json()
        if "error" in answer:
            raise QMPError(answer['error'])
        return answer['return']

@attr.s(eq=False)
class QMPError(Exception):
    msg = attr.ib(validator=attr.validators.instance_of(str))
