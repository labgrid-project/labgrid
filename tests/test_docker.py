"""
Test labgrid code of communicating with a docker daemon and using it
for creating, starting and accessing a docker container.
"""

import pytest
import docker
import io

from labgrid import Environment
from labgrid.driver import DockerDriver
from labgrid.resource.docker import DockerConstants
from labgrid.exceptions import NoResourceFoundError

pytest.importorskip("docker")


def check_external_progs_present():
    """Determine if host machine has a usable docker daemon"""
    try:
        import docker
        try:
            dock = docker.from_env()
            dock.info()
        except docker.errors.DockerException:
            return False
    except OSError:
        return False
    return True


@pytest.fixture
def docker_env(tmp_path_factory):
    """Create Environment instance from the given inline YAML file."""
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    # Note: The SSHDriver part at bottom is only used by the test that
    # will run if a docker daemon is present, not by
    # test_driver_without_daemon.
    p.write_text(
        """
        targets:
          main:
            resources:
            - DockerDaemon:
                docker_daemon_url: "unix:///var/run/docker.sock"
            drivers:
            - DockerDriver:
                image_uri: "rastasheep/ubuntu-sshd:16.04"
                pull: 'missing'
                container_name: "ubuntu-lg-example"
                host_config: {"network_mode": "bridge"}
                network_services: [
                  {"port": 22, "username": "root", "password": "root"}]
            - DockerStrategy: {}
            - SSHDriver:
                keyfile: ""
        """
    )
    return Environment(str(p))


@pytest.fixture
def docker_env_for_local_container(tmp_path_factory):
    """Create Environment instance from the given inline YAML file."""
    p = tmp_path_factory.mktemp("docker") / "config.yaml"
    p.write_text(
        """
        targets:
          main:
            resources:
            - DockerDaemon:
                docker_daemon_url: "unix:///var/run/docker.sock"
            drivers:
            - DockerDriver:
                image_uri: "local_rastasheep"
                pull: "never"
                container_name: "ubuntu-lg-example"
                host_config: {"network_mode": "bridge"}
                network_services: [
                  {"port": 22, "username": "root", "password": "root"}]
            - DockerStrategy: {}
            - SSHDriver:
                keyfile: ""
        """
    )
    return Environment(str(p))


@pytest.fixture
def docker_target(docker_env):
    """Get a labgrid Target instance from the Environment instance
    given by docker_env. When tearing down the Target instance, make sure
    singleton ResourceManager is "reset".
    """
    t = docker_env.get_target()
    yield t

    # Fake! In real life, ResourceManager is intended to be a singleton.
    # The class is created only once - when python parses common.py.
    # But this means that the class with its "instances" attribute survives
    # from test case to test case. This is not what we want. On the contrary,
    # we want each of test_docker_with_daemon and test_docker_without_daemon
    # to run with a *fresh* instance of the ResourceManager singleton.
    #
    # Luckily it is easy to "reset" ResourceManager. The singleton is kept
    # in attribute "instances" so by resetting "instances" to {}, next test
    # case will force creation of a fresh ResourceManager instance.
    from labgrid.resource import ResourceManager
    ResourceManager.instances = {}


@pytest.fixture
def command(docker_target):
    """Bring system to a state where it's possible to execute commands
    on a running docker container. When done, stop the container again.
    """
    strategy = docker_target.get_driver('DockerStrategy')
    strategy.transition("accessible")
    shell = docker_target.get_driver('CommandProtocol')
    yield shell
    strategy.transition("gone")


@pytest.fixture
def docker_target_for_local_image(docker_env_for_local_container):
    """Same as `docker_target` but uses a different image uri"""
    t = docker_env_for_local_container.get_target()
    yield t

    from labgrid.resource import ResourceManager
    ResourceManager.instances = {}


@pytest.fixture
def local_command(docker_target_for_local_image):
    """Same as `command` but uses a different image uri"""
    strategy = docker_target_for_local_image.get_driver('DockerStrategy')
    strategy.transition("accessible")
    shell = docker_target_for_local_image.get_driver('CommandProtocol')
    yield shell
    strategy.transition("gone")

@pytest.mark.skipif(not check_external_progs_present(),
                    reason="No access to a docker daemon")
def test_docker_with_daemon(command):
    """Test the docker machinery when a running docker daemon can be used
    (thus test is skipped if there is no such daemon). The tests executes
    a few tests inside a running docker container using SSHDriver for access.
    """
    stdout, stderr, return_code = command.run('cat /proc/version')
    assert return_code == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]

    stdout, stderr, return_code = command.run('false')
    assert return_code != 0
    assert len(stdout) == 0
    assert len(stderr) == 0


@pytest.fixture
def build_image():
    client = docker.from_env()
    dockerfile_content = """
    FROM rastasheep/ubuntu-sshd:16.04
    """
    dockerfile_stream = io.BytesIO(dockerfile_content.encode("utf-8"))
    image, logs = client.images.build(fileobj=dockerfile_stream, tag="local_rastasheep", rm=True)


@pytest.mark.skipif(not check_external_progs_present(),
                    reason="No access to a docker daemon")
def test_docker_with_daemon_and_local_image(build_image, local_command):
    """Build a container locally and connect to it"""
    stdout, stderr, return_code = local_command.run('cat /proc/version')
    assert return_code == 0
    assert len(stdout) > 0
    assert len(stderr) == 0
    assert 'Linux' in stdout[0]

    stdout, stderr, return_code = local_command.run('false')
    assert return_code != 0
    assert len(stdout) == 0
    assert len(stderr) == 0


def test_create_driver_fail_missing_docker_daemon(target):
    """The test target does not contain any DockerDaemon instance -
    and so creation must fail.
    """
    with pytest.raises(NoResourceFoundError):
        DockerDriver(target, "docker_driver")


def test_docker_without_daemon(docker_env, mocker):
    """Test as many aspects as possible of DockerDriver, DockerDaemon,
    DockerManager and DockerStrategy without using an actual
    docker daemon, real sockets or system time"""

    # Target::update_resources() and Target::await_resources use
    # time.monotonic() and time.sleep() to control when to search
    # for resources. Avoid time delays and make running from cmd-line
    # and inside debugger equal by mocking out all time.
    time_monotonic = mocker.patch('labgrid.target.monotonic')
    time_monotonic.side_effect = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

    # Mock actions on the imported "docker" python module
    docker_client_class = mocker.patch('docker.DockerClient',
                                       autospec=True)
    docker_client = docker_client_class.return_value
    api_client_class = mocker.patch('docker.api.client.APIClient',
                                    autospec=True)
    docker_client.api = api_client_class.return_value
    api_client = docker_client.api
    api_client.base_url = "unix:///var/run/docker.sock"
    # First, a "mocked" old docker container is returned by
    # ...api.containers(); this is done when DockerDaemon tries
    # to clean up old containers. Next, a one-item list is delivered by
    # ...api.containers() which is part of DockerDaemon::update_resources()
    # - it is cached for future use; therefore no need to replicate
    # this entry in the side_effects list.
    api_client.containers.side_effect = [
        [{'Labels': {DockerConstants.DOCKER_LG_CLEANUP_LABEL:
                     DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
          'NetworkSettings': {'IPAddress': '1.1.1.1'},
          'Names': 'old-one',
          'Id': '0'
          }],
        [{'Labels': {DockerConstants.DOCKER_LG_CLEANUP_LABEL:
                     DockerConstants.DOCKER_LG_CLEANUP_TYPE_AUTO},
          'NetworkSettings': {'IPAddress': '2.1.1.1'},
          'Names': 'actual-one',
          'Id': '1'
          }]
    ]
    docker_client.images.get.side_effect = docker.errors.ImageNotFound(
        "Image not found", response=None, explanation="")

    # Mock actions on the imported "socket" python module
    socket_create_connection = mocker.patch('socket.create_connection')
    sock = mocker.MagicMock()
    # First two negative connection setup attempts are used at initial
    # resource setup during strategy.transition("shell"); these simulate
    # that it takes time for the docker container to come up. The final,
    # successful, return value is delivered when t.update_resources()
    # is called explicitly later on.
    socket_create_connection.side_effect = [
        Exception('No connection on first call'),
        Exception('No connection on second call'),
        sock]

    # get_target() - which calls make_target() - creates resources/drivers
    # from .yaml configured environment. Creation provokes binding
    # and attempts to connect to network services.
    api_client.remove_container.assert_not_called()
    t = docker_env.get_target()
    assert api_client.remove_container.call_count == 1

    # Make sure DockerDriver didn't accidentally succeed with a socket connect
    # attempt (this fact is actually expressed by what happens next -
    # the socket is closed).
    sock.shutdown.assert_not_called()
    sock.close.assert_not_called()

    # Get strategy - needed to transition to "shell" state.
    strategy = t.get_driver("DockerStrategy")

    # strategy starts in state "unknown" so the following should be a no-op.
    strategy.transition("unknown")

    # Now activate DockerDriver and set it "on". This creates and starts
    # a (mocked) container.
    strategy.transition("accessible")

    # Assert what mock calls transitioning to "shell" must have caused
    #
    # DockerDriver::on_activate():
    image_uri = t.get_driver('DockerDriver').image_uri
    docker_client.images.get.assert_called_once_with(image_uri)
    docker_client.images.pull.assert_called_once_with(image_uri)

    assert api_client.create_host_config.call_count == 1
    assert api_client.create_container.call_count == 1
    #
    # DockerDriver::on()
    assert api_client.start.call_count == 1

    # From here the test using the real docker daemon would proceed with
    #   shell = t.get_driver('CommandProtocol')
    #   shell.run('...')
    # which makes use of e.g. the SSHDriver.  Binding the SSHDriver
    # is important since it triggers activation of the NetworkService.
    # But then SSHDriver uses ssh to connect to the NetworkService
    # which will lead to error. Instead just call update_resources()
    # directly - which is what is needed to provoke DockerDaemon to create
    # a new NetworkService instance.
    t.update_resources()

    # This time socket connection was successful
    # (per the third socket_create_connection return value defined above).
    assert sock.shutdown.call_count == 1
    assert sock.close.call_count == 1

    # Bonus: Test what happens if taking a forbidden strategy transition:
    # "shell" -> "unknown".
    from labgrid.strategy import StrategyError
    with pytest.raises(StrategyError):
        strategy.transition("unknown")

    # Also bonus: How are invalid state names handled?
    with pytest.raises(KeyError):
        strategy.transition("this is not a valid state")

    # Return to "gone" state - to also use that part of the DockerDriver code.
    strategy.transition("gone")
    from labgrid.strategy.dockerstrategy import Status
    assert strategy.status == Status.gone
