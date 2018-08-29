import attr
import logging
import docker
import socket

from labgrid.util.dict import find
from .networkservice import NetworkService
from ..factory import target_factory
from .common import ManagedResource, ResourceManager

class DockerConstants():
    # Class constants for handling container cleanup
    DOCKER_LG_CLEANUP_LABEL = "lg_cleanup"
    # Currently only a single cleanup routine is implemented which removes all labgrid created containers on each
    # test run. In the future more sophisticated mechanisms could be implemented by adding more cleanup types.
    DOCKER_LG_CLEANUP_TYPE_AUTO = "auto"

@attr.s(cmp=False)
class DockerManager(ResourceManager):
    """
    The DockerManager is responsible for cleaning up dangling containers and managing the managed
    DockerNetworkService resources. Different docker daemons for different targets are allowed, but there has to be
    only one for each target.
    """

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.log = logging.getLogger('DockerManager')
        self._client = dict()
        self._docker_daemons_cleaned = list()

    def on_resource_added(self, resource):
        """
        If the resource added is a DockerDaemon make sure this is the only one added for this target. If it is
        create a docker client to be used to communicate with the docker daemon.
        If the resource added is a DockerNetworkService validate a DockerDaemon exist for the target.
        """
        if isinstance(resource, DockerDaemon):
            if resource.target.name in self._client:
                raise EnvironmentError("Only one docker daemon is allowed for each target")
            self._client[resource.target.name] = docker.DockerClient(base_url=resource.docker_daemon_url)
            self._container_cleanup(self._client[resource.target.name])
            resource.avail = True
        else:
            if not self._client[resource.target.name]:
                raise EnvironmentError("Missing docker daemon resource")

    def poll(self):
        for resource in self.resources:
            if not isinstance(resource, DockerDaemon):
                resource.on_poll(self._client[resource.target.name])

    def _container_cleanup(self, docker_client):
        """
        Fetches a list of containers from the daemon. Each container that has the label DOCKER_LG_CLEANUP_LABEL
        is removed. This is for cleanup of potential dangling containers left over from earlier test runs.
        """
        if docker_client.api.base_url not in self._docker_daemons_cleaned:
            container_list = docker_client.api.containers(
                all=True, filters={"label": DockerConstants.DOCKER_LG_CLEANUP_LABEL})
            for container in container_list:
                if container['Labels'][DockerConstants.DOCKER_LG_CLEANUP_LABEL] == DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO:
                    self.log.info("Deleting container " + container['Names'][0])
                    docker_client.api.remove_container(container['Id'], force=True)
            self._docker_daemons_cleaned.append(docker_client.api.base_url)


@target_factory.reg_resource
@attr.s(cmp=False)
class DockerDaemon(ManagedResource):
    manager_cls = DockerManager
    """ A ressource identifying a docker daemon """
    docker_daemon_url = attr.ib(validator=attr.validators.instance_of(str))


@target_factory.reg_resource
@attr.s(cmp=False)
class DockerNetworkService(ManagedResource, NetworkService):
    """
    The docker network service is a managed resource mapping a container name to a network service.
    """
    manager_cls = DockerManager
    container_name = attr.ib(default=None, validator=attr.validators.instance_of(str))
    address = attr.ib(default="", validator=attr.validators.in_([""]))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.log = logging.getLogger('DockerContainer')
        self.timeout = 5.0

    def on_poll(self, docker_client):
        self._update_resource(docker_client)

    def _update_resource(self, docker_client):
        """
        Update resource takes a docker client and uses this to lookup a container by name. If the container exists
        the IP address is looked up by inspecting the docker container. If an IP address is found the address is filled
        in the NetworkService base class and the resource is identified as available.
        :param docker_client: The docker client to use for lookup
        """
        if self.address == "":
            container = docker_client.api.containers(filters={"name": "/"+self.container_name})
            self.log.debug("Containers found {}".format(container))
            if container:
                self.address = find(d=container[0]['NetworkSettings'], key='IPAddress')
                self.log.debug("setting ip address %s for target %s", self.address, self.target.name)
        if self.address != "" and self._socket_connect(self.address, self.port):
            self.avail = True
        else:
            self.avail = False

    def _socket_connect(self, address, port):
        """
        Try to do a socket connect
        :param address: The ip address to connect to
        :param port: The port to connect to
        :return: True on successfull connection false if failed
        """
        try:
            s = socket.create_connection((address, port))
        except Exception as e:
            self.log.debug("Socket connect failed {}:{} - {}".format(address, port, e))
            return False
        s.shutdown(socket.SHUT_RDWR)
        s.close()
        self.log.debug("Socket connect successfull {}:{}".format(address, port))
        return True
