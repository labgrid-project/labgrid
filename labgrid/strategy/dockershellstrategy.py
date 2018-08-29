import attr

from ..factory import target_factory
from .common import StrategyError
from ..driver.dockerdriver import DockerDriver
from .shellstrategy import ShellStrategy, Status


@target_factory.reg_driver
@attr.s(cmp=False)
class DockerShellStrategy(ShellStrategy):
    """
    The DockerShellStrategy is a shellstrategy for docker containers. The strategy controls a docker container by using
    the bound docker driver instance.
    """
    bindings = {
        "docker_driver": DockerDriver,
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    def transition(self, status):
        if not isinstance(status, Status):
            status = Status[status]
        if status == self.status:
            return  # nothing to do
        elif status == Status.shell:
            self.target.activate(self.docker_driver)
            self.docker_driver.start_container()
        elif status == Status.off:
            self.target.activate(self.docker_driver)
            self.docker_driver.stop_container()
        else:
            raise StrategyError(
                "no transition found from {} to {}".
                format(self.status, status)
            )
        self.status = status
