"""
Class for connecting to a docker daemon running on the host machine.
"""
from enum import Enum

import attr

from labgrid.factory import target_factory
from labgrid.driver.common import Driver
from labgrid.resource.docker import DockerConstants
from labgrid.protocol.powerprotocol import PowerProtocol


class PullPolicy(Enum):
    """Pull policy for the `DockerDriver`.

    Modelled after `podman run --pull` / `docker run --pull`.

    * always: Always pull the image and throw an error if the pull fails.
    * missing: Pull the image only when the image is not in the local
      containers storage. Throw an error if no image is found and the pull
      fails.
    * never: Never pull the image but use the one from the local containers
      storage. Throw an error if no image is found.
    * newer: **Note** not supported by the driver, and therefore not
      implemented.
    """
    Always = 'always'
    Missing = 'missing'
    Never = 'never'

def pull_policy_converter(value):
    if isinstance(value, PullPolicy):
        return value
    try:
        return PullPolicy(value)
    except ValueError:
        raise ValueError(f"Invalid pull policy: {value}")


@target_factory.reg_driver
@attr.s(eq=False)
class DockerDriver(PowerProtocol, Driver):
    """The DockerDriver is used to create docker containers.
    This is done via communication with a docker daemon.

    When a container is created the container is labeled with an
    cleanup strategy identifier. Currently only one strategy is
    implemented.  This strategy simply deletes all labgrid created
    containers before each test run. This is to ensure cleanup of
    dangling containers from crashed tests or hanging containers.

    Image pruning is not done by the driver.

    For detailed information about the arguments see the
    "Docker SDK for Python" documentation
    https://docker-py.readthedocs.io/en/stable/containers.html#container-objects

    Args:
        bindings (dict): The labgrid bindings
    Args passed to docker.create_container:
        image_uri (str): The uri of the image to fetch
        pull (str): Pull policy. Default policy is `always` for backward
        compatibility concerns
        command (str): The command to execute once container has been created
        volumes (list): The volumes to declare
        environment (list): Docker environment variables to set
        host_config (dict): Docker host configuration parameters
        network_services (list): Sequence of dicts each specifying a network \
                                 service that the docker container exposes.

    """
    bindings = {"docker_daemon": {"DockerDaemon"}}
    image_uri = attr.ib(default=None, validator=attr.validators.optional(
        attr.validators.instance_of(str)))
    pull = attr.ib(default=PullPolicy.Always,
        converter=pull_policy_converter)
    command = attr.ib(default=None, validator=attr.validators.optional(
        attr.validators.instance_of(str)))
    volumes = attr.ib(default=None, validator=attr.validators.optional(
        attr.validators.instance_of(list)))
    container_name = attr.ib(default=None, validator=attr.validators.optional(
        attr.validators.instance_of(str)))
    environment = attr.ib(
        default=None, validator=attr.validators.optional(
            attr.validators.instance_of(list)))
    host_config = attr.ib(
        default=None, validator=attr.validators.optional(
            attr.validators.instance_of(dict)))
    network_services = attr.ib(
        default=None, validator=attr.validators.optional(
            attr.validators.instance_of(list)))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self._client = None
        self._container = None

    def on_activate(self):
        """ On activation:
        1. Import docker module (_client and _container remain available)
        2. Connect to the docker daemon
        3. Pull requested image from docker registry if needed
        4. Create the new container according to parameters from conf
        """
        import docker
        self._client = docker.DockerClient(
            base_url=self.docker_daemon.docker_daemon_url)

        if self.pull == PullPolicy.Always:
            self._client.images.pull(self.image_uri)
        elif self.pull == PullPolicy.Missing:
            try:
                self._client.images.get(self.image_uri)
            except docker.errors.ImageNotFound:
                self._client.images.pull(self.image_uri)
        elif self.pull == PullPolicy.Never:
            self._client.images.get(self.image_uri)

        self._container = self._client.api.create_container(
            self.image_uri,
            command=self.command,
            volumes=self.volumes,
            name=self.container_name,
            environment=self.environment,
            labels={
                DockerConstants.DOCKER_LG_CLEANUP_LABEL:
                DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
            host_config=self._client.api.create_host_config(
                **self.host_config))

    def on_deactivate(self):
        """ Remove container after use"""
        self._client.api.remove_container(self._container.get('Id'),
                                          force=True)
        self._client = None
        self._container = None

    def on(self):
        """ Start the container created during activation """
        self._client.api.start(container=self._container.get('Id'))

    def off(self):
        """ Stop the container created during activation """
        self._client.api.stop(container=self._container.get('Id'))

    def cycle(self):
        """Cycle the docker container by stopping and starting it"""
        self.off()
        self.on()
