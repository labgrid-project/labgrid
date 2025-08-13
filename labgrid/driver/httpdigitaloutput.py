import re
from importlib import import_module

import attr

from ..factory import target_factory
from ..protocol import DigitalOutputProtocol
from ..step import step
from ..util.proxy import proxymanager
from .common import Driver
from .exception import ExecutionError


@target_factory.reg_driver
@attr.s(eq=False)
class HttpDigitalOutputDriver(Driver, DigitalOutputProtocol):
    bindings = { "http": "HttpDigitalOutput" }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._requests = import_module("requests")

    def on_activate(self):
        self._url_set = proxymanager.get_url(
            self.http.url,
            default_port=(443 if self.http.url.startswith("https") else 80),
        )

        if self.http.url_get:
            self._url_get = proxymanager.get_url(
                self.http.url_get,
                default_port=(443 if self.http.url_get.startswith("https") else 80),
            )

        else:
            self._url_get = self._url_set

    @Driver.check_active
    @step(args=["status"])
    def set(self, status):
        method = self.http.method or "PUT"
        body = self.http.body_asserted if status else self.http.body_deasserted

        res = self._requests.request(method, self._url_set, data=body)
        res.raise_for_status()

    @Driver.check_active
    @step(result=["True"])
    def get(self):
        res = self._requests.get(self._url_get)
        res.raise_for_status()

        # Check if the response body matches an asserted state
        if self.http.body_get_asserted:
            if re.fullmatch(self.http.body_get_asserted, res.text) is not None:
                return True

        elif res.text == self.http.body_asserted:
            return True

        # Check if the response body matches a de-asserted state
        if self.http.body_get_deasserted:
            if re.fullmatch(self.http.body_get_deasserted, res.text) is not None:
                return False

        elif res.text == self.http.body_deasserted:
            return False

        raise ExecutionError(
            f'response does not match asserted or deasserted state: "{res.text}"'
        )
