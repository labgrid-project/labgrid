import json

import attr
import requests as r

@attr.s
class HawkbitTestClient:
    host = attr.ib(validator=attr.validators.instance_of(str))
    port = attr.ib(validator=attr.validators.instance_of(str))
    username = attr.ib(validator=attr.validators.instance_of(str))
    password = attr.ib(validator=attr.validators.instance_of(str))
    version = attr.ib(
        default=1.0, validator=attr.validators.instance_of(float)
    )

    def __attrs_post_init__(self):
        self.url = 'http://{host}:{port}/rest/v1/{endpoint}'

    def add_target(self, device_address: str, token: str):
        """Add a target to the HawkBit Installation

        Arguments:
          - device_address: the device address of the added target
          - token: token to uniquely identify the target
        """
        testdata = [{
            'controllerId': "1",
            'name': 'TestTarget {}'.format(self.version),
            'description': 'test',
            'address': device_address,
            'securityToken': token
        }]

        self.post_json('targets', testdata)

    def add_swmodule(self):
        testdata = [{
            'name': 'Test_module {}'.format(self.version),
            'version': str(self.version),
            'type': 'os'
        }]

        self.module_id = self.post_json('softwaremodules', testdata)[0]['id']

    def add_distributionset(self):
        if not self.module_id:
            raise HawkbiError("No softwaremodule added")
        testdata = [{
            'name': 'Test_distribution {}'.format(self.version),
            'description': 'Test distribution',
            'version': str(self.version),
            'modules': [{
                'id': self.module_id
            }],
            'type': 'os'
        }]

        self.distribuion_id = self.post_json('distributionsets',
                                             testdata)[0]['id']

    def add_artifact(self, filename: str):
        if not self.module_id:
            raise HawkbiError("No softwaremodule added")
        endpoint = 'softwaremodules/{}/artifacts'.format(self.module_id)

        self.post_binary(endpoint, filename)

    def assign_target(self):
        if not self.distribution_id:
            raise HawkbiError("No distribution added")
        endpoint = 'distribuionsets/{}/assignedTargets'.format(
            self.distribution_id
        )
        testdata = [{'id': '1'}]

        self.post_json(endpoint, testdata)
        # Increment version to be able to flash over an already deployed distribution
        self.version = self.version + 0.1

    def post_json(self, endpoint: str, data: dict):
        headers = {'Content-Type': 'application/json;charset=UTF-8'}
        req = r.post(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            headers=headers,
            auth=(self.username, self.password),
            json=data
        )
        if req.status_code != 201:
            raise HawkbiError(
                'Wrong statuscode, got {} instead of 201, with error {}'.
                format(req.status_code, req.json())
            )
        return req.json()

    def post_binary(self, endpoint: str, filename: str):
        files = {'file': open(filename, 'rb')}
        req = r.post(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            auth=(self.username, self.password),
            files=files
        )
        if req.status_code != 201:
            raise HawkbiError(
                'Wrong statuscode, got {} instead of 201, with error {}'.
                format(req.status_code, req.json())
            )
        return req.json()

    def get_endpoint(self, endpoint: str):
        req = r.get(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            headers=headers,
            auth=(self.username, self.password)
        )
        if req.status_code != 200:
            raise HawkbiError(
                'Wrong statuscode, got {} instead of 200, with error {}'.
                format(req.status_code, req.json())
            )
        return req.json()


@attr.s
class HawkbiError(Exception):
    msg = attr.ib()
