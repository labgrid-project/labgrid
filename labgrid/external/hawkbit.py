import attr
import requests as r

@attr.s(cmp=False)
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

    def add_target(self, target_id: str, token: str):
        """Add a target to the HawkBit Installation

        Arguments:
          - target_id(str): the (unique) device name of the target to add
          - token(str): pre-shared key to authenticate the target
        """
        testdata = [{
            'controllerId': target_id,
            'name': target_id,
            'description': 'test',
            'securityToken': token
        }]

        self.post_json('targets', testdata)

    def delete_target(self, target_id: str):
        """Delete a target from the HawkBit Installation

        Arguments:
          - target_id(str): the (unique) device name of the target to delete
        """

        self.delete('targets/{}'.format(target_id))

    def add_swmodule(self, modulename: str):
        testdata = [{
            'name': modulename,
            'version': str(self.version),
            'type': 'os'
        }]

        self.module_id = self.post_json('softwaremodules', testdata)[0]['id']
        return self.module_id

    def delete_swmodule(self, module_id: str):
        """Delete a softwaremodule from the HawkBit Installation

        Arguments:
          - module_id(str): the ID given by hawkBit for the module
        """

        self.delete('softwaremodules/{}'.format(module_id))

    def add_distributionset(self, module_id, name=None):
        testdata = [{
            'name': name if name else 'Test_distribution {}'.format(self.version),
            'description': 'Test distribution',
            'version': str(self.version),
            'modules': [{
                'id': module_id
            }],
            'type': 'os'
        }]

        self.distribution_id = self.post_json('distributionsets',
                                              testdata)[0]['id']
        return self.distribution_id

    def delete_distributionset(self, distset_id: str):
        """Delete a distrubitionset from the HawkBit Installation

        Arguments:
          - distset_id(str): the ID of the distribution set to delete
        """

        self.delete('distributionsets/{}'.format(distset_id))

    def add_artifact(self, module_id: str, filename: str):
        endpoint = 'softwaremodules/{}/artifacts'.format(module_id)

        return self.post_binary(endpoint, filename)['id']

    def delete_artifact(self, module_id: str, artifact_id: str):
        """Delete an artifact from the HawkBit Installation

        Arguments:
          - artifact_id(str): the ID of the artifact to delete
        """

        self.delete('softwaremodules/{}/artifacts/{}'.format(module_id, artifact_id))

    def assign_target(self, distribution_id, target_id):
        endpoint = 'distributionsets/{}/assignedTargets'.format(
            distribution_id
        )
        testdata = [{'id': target_id}]

        self.post_json(endpoint, testdata)
        # Increment version to be able to flash over an already deployed distribution
        self.version = self.version + 0.1

    def add_rollout(self, name, distribution_id, groups):
        testdata = {
            'name': name,
            'distributionSetId': distribution_id,
            'targetFilterQuery': 'id==*',
            'amountGroups': groups
        }

        self.rollout_id = self.post_json('rollouts', testdata)['id']
        return self.rollout_id

    def start_rollout(self, rollout_id):
        endpoint = 'rollouts/{}/start'.format(
            rollout_id
        )

        self.post(endpoint)

    def post(self, endpoint: str):
        req = r.post(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            auth=(self.username, self.password),
        )
        if req.status_code != 200 and req.status_code != 201:
            raise HawkbitError(
                'Wrong statuscode, got {} instead of 200/201'.
                format(req.status_code)
            )

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
        if req.status_code != 200 and req.status_code != 201:
            raise HawkbitError(
                'Wrong statuscode, got {} instead of 200/201, with error {}'.
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
            raise HawkbitError(
                'Wrong statuscode, got {} instead of 201, with error {}'.
                format(req.status_code, req.json())
            )
        return req.json()

    def delete(self, endpoint: str):
        req = r.delete(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            auth=(self.username, self.password),
        )
        if req.status_code != 200:
            raise HawkbitError(
                'Wrong statuscode, got {} instead of 200, with error {}'.
                format(req.status_code, req.json())
            )

    def get_endpoint(self, endpoint: str):
        headers = {'Content-Type': 'application/json;charset=UTF-8'}
        req = r.get(
            self.url.format(
                endpoint=endpoint, host=self.host, port=self.port
            ),
            headers=headers,
            auth=(self.username, self.password)
        )
        if req.status_code != 200:
            raise HawkbitError(
                'Wrong statuscode, got {} instead of 200, with error {}'.
                format(req.status_code, req.json())
            )
        return req.json()


@attr.s(cmp=False)
class HawkbitError(Exception):
    msg = attr.ib()
