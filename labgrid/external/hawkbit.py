import requests as r
import json

HOST = 'localhost'
PORT = '8080'
USERNAME = 'admin'
PASSWORD = 'admin'

class HawkbitTestClient:
    def __init__(self):
        self.host = HOST
        self.port = PORT
        self.auth = (USERNAME, PASSWORD)
        self.version = 1.0
        self.url = 'http://{host}:{port}/rest/v1/{endpoint}'

    def add_target(self, device_address, token):
        testdata = [ { 'controllerId': "1"
                       ,'name': 'TestTarget {}'.format(self.version)
                       ,'description': 'test'
                       ,'address': device_address
                       ,'securityToken': token } ]

        self.post_json('targets', testdata)

    def add_swmodule(self):
        testdata = [ { 'name': 'Test_module {}'.format(self.version)
                       ,'version': str(self.version)
                       ,'type': 'os'} ]

        self.module_id = self.post_json('softwaremodules', testdata)[0]['id']

    def add_distributionset(self):
        if not self.module_id:
            raise HawkbitException("No softwaremodule added")
        testdata = [ { 'name': 'Test_distribution {}'.format(self.version)
                       ,'description': 'Test distribution'
                       ,'version': str(self.version)
                       , 'modules': [{'id': self.module_id}]
                       ,'type': 'os'} ]

        self.distribuion_id = self.post_json('distributionsets', testdata)[0]['id']

    def add_artifact(self, filename):
        if not self.module_id:
            raise HawkbitException("No softwaremodule added")
        endpoint = 'softwaremodules/{}/artifacts'.format(self.module_id)

        self.post_binary(endpoint, filename)

    def assign_target(self):
        if not self.distribution_id:
            raise HawkbitException("No distribution added")
        endpoint = 'distribuionsets/{}/assignedTargets'.format(self.distribution_id)
        testdata = [{ 'id': '1' }]

        self.post_json(endpoint, testdata)
        # Increment version to be able to flash over an already deployed distribution
        self.version = self.version + 0.1

    def post_json(self, endpoint, data):
        headers = {'Content-Type': 'application/json;charset=UTF-8' }
        req = r.post(self.url.format(endpoint=endpoint, host=self.host,port=self.port), headers=headers, auth=self.auth, json=data)
        if req.status_code != 201:
            raise HawkbitException('Wrong statuscode, got {} instead of 201, with error {}'.format(req.status_code, req.json()))
        return req.json()

    def post_binary(self, endpoint, filename):
        files = { 'file': open(filename, 'rb') }
        req = r.post(self.url.format(endpoint=endpoint,host=self.host,port=self.port), auth=self.auth, files=files)
        if req.status_code != 201:
            raise HawkbitException('Wrong statuscode, got {} instead of 201, with error {}'.format(req.status_code, req.json()))
        return req.json()

    def get_endpoint(self, endpoint):
        req = r.get(self.url.format(endpoint=endpoint,host=self.host,port=self.port), headers=headers, auth=self.auth)
        if req.status_code != 200:
            raise HawkbitException('Wrong statuscode, got {} instead of 200, with error {}'.format(req.status_code, req.json()))
        return req.json()



class HawkbitException(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __repr__(self):
        return "HawkbitException({msg})".format(msg=self.msg)
