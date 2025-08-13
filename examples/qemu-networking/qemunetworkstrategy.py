# Copyright 2023 by Garmin Ltd. or its subsidiaries
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import enum

import attr

from labgrid import target_factory, step
from labgrid.strategy import Strategy, StrategyError
from labgrid.util import get_free_port


class Status(enum.Enum):
    unknown = 0
    off = 1
    shell = 2


@target_factory.reg_driver
@attr.s(eq=False)
class QEMUNetworkStrategy(Strategy):
    bindings = {
        "qemu": "QEMUDriver",
        "shell": "ShellDriver",
        "ssh": "SSHDriver",
    }

    status = attr.ib(default=Status.unknown)

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        self.__port_forward = None
        self.__remote_port = self.ssh.networkservice.port

    @step(result=True)
    def get_remote_address(self):
        return str(self.shell.get_ip_addresses()[0].ip)

    @step()
    def update_network_service(self):
        new_address = self.get_remote_address()
        networkservice = self.ssh.networkservice

        if networkservice.address != new_address:
            self.target.deactivate(self.ssh)

            if "user" in self.qemu.nic.split(","):
                if self.__port_forward is not None:
                    self.qemu.remove_port_forward(*self.__port_forward)

                local_port = get_free_port()
                local_address = "127.0.0.1"

                self.qemu.add_port_forward(
                    "tcp",
                    local_address,
                    local_port,
                    new_address,
                    self.__remote_port,
                )
                self.__port_forward = ("tcp", local_address, local_port)

                networkservice.address = local_address
                networkservice.port = local_port
            else:
                networkservice.address = new_address
                networkservice.port = self.__remote_port

    @step(args=["state"])
    def transition(self, state, *, step):
        if not isinstance(state, Status):
            state = Status[state]

        if state == Status.unknown:
            raise StrategyError(f"can not transition to {state}")

        elif self.status == state:
            step.skip("nothing to do")
            return

        if state == Status.off:
            self.target.activate(self.qemu)
            self.qemu.off()

        elif state == Status.shell:
            self.target.activate(self.qemu)
            self.qemu.on()
            self.target.activate(self.shell)
            self.update_network_service()

        self.status = state
