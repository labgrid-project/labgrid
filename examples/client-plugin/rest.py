"""Example lab-specific REST resource, driver and client command."""

import json
import urllib.error
import urllib.request

import attr

from labgrid import target_factory
from labgrid.driver import Driver
from labgrid.driver.exception import ExecutionError
from labgrid.remote.client_commands import client_command
from labgrid.resource import Resource
from labgrid.step import step


@target_factory.reg_resource
@attr.s(eq=False)
class ExampleRestResource(Resource):
    url = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_driver
@attr.s(eq=False)
class ExampleRestDriver(Driver):
    bindings = {"rest": "ExampleRestResource"}

    def _request(self, method, path, data=None):
        url = self.rest.url.rstrip("/") + "/" + path.lstrip("/")
        body = None if data is None else data.encode()
        request = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.loads(response.read())
        except urllib.error.URLError as error:
            raise ExecutionError(f"{method} {url} failed: {error}") from error

    @Driver.check_active
    @step(args=["path"])
    def get(self, path):
        return self._request("GET", path)

    @Driver.check_active
    @step(args=["path", "data"])
    def post(self, path, data=None):
        return self._request("POST", path, data)


@client_command("rest")
class RestCommand:
    """query the example REST interface"""

    @staticmethod
    def add_arguments(subparser):
        subparser.add_argument("method", choices=["get", "post"])
        subparser.add_argument("path")
        subparser.add_argument("--data", help="JSON request body for post")

    @staticmethod
    def run(session, place, target):
        driver = target.get_driver("ExampleRestDriver")
        args = session.args
        result = driver.get(args.path) if args.method == "get" else driver.post(args.path, args.data)
        print(json.dumps(result))
