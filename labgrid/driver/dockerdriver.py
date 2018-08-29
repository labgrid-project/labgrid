import attr
import docker
import logging

from labgrid.factory import target_factory
from labgrid.driver.common import Driver
from labgrid.resource.docker import DockerDaemon, DockerConstants


@target_factory.reg_driver
@attr.s(cmp=False)
class DockerDriver(Driver):
    """
    The DockerDriver is used to control a docker daemon

    When a container is created the container is labeled with an cleanup strategy identifer. Currently only one
    strategy is implemented. This strategy simply deletes all labgrid created containers before each test run.
    This is to ensure cleanup of dangling containers from crashed tests or hanging containers.

    Image pruning is not done by the driver.

    For detailed information about the arguments see the "Docker SDK for Python" documentation
    https://docker-py.readthedocs.io/en/3.3.0/api.html#module-docker.api.container
    
    Args:
        bindings (dict): The labgrid bindings
    Args passed to docker.create_container:
        image_uri (str): The uri of the image to fetch
        command (str): The command to execute once container has been created
        volumes (list): The volumes to declare
        entrypoint (str): Docker container entry point
        environment (list): Docker environment variables to set
        host_config (dict): Docker host configuration parameters
    """
    bindings = {"docker_daemon": {DockerDaemon}}
    image_uri = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    command = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    volumes = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(list)))
    container_name = attr.ib(default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    entrypoint = attr.ib(
        default=None, validator=attr.validators.optional(attr.validators.instance_of(str)))
    environment = attr.ib(
        default=None, validator=attr.validators.optional(attr.validators.instance_of(list)))
    host_config = attr.ib(
        default=None, validator=attr.validators.optional(attr.validators.instance_of(dict)))

    def __attrs_post_init__(self):
        self.logger = logging.getLogger("{}({})".format(self, self.target))
        super().__attrs_post_init__()
        self._client = None
        self._container = None

    def on_activate(self):
        """
        On activation
        1. Connect to the docker daemon
        2. Pull requested image from docker registry if needed
        3. Create the new container according to parameters from conf
        """
        self._client = docker.DockerClient(
            base_url=self.docker_daemon.docker_daemon_url)
        self._client.images.pull(self.image_uri)
        self._container = self._client.api.create_container(
            self.image_uri,
            command=self.command,
            volumes=self.volumes,
            name=self.container_name,
            entrypoint=self.entrypoint,
            environment=self.environment,
            labels={
                DockerConstants.DOCKER_LG_CLEANUP_LABEL: DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
            host_config=self._client.api.create_host_config(**self.host_config))

    def on_deactivate(self):
        """ Remove container after use"""
        self._client.api.remove_container(self._container.get('Id'), force=True)
        self._client = None
        self._container = None

    def start_container(self):
        """ Start the container created during activation """
        self._client.api.start(container=self._container.get('Id'))

    def stop_container(self):
        """ Stop the container created during activation """
        self._client.api.stop(container=self._container.get('Id'))
