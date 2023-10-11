import logging

from labgrid import Environment

logging.basicConfig(
        level=logging.DEBUG
)

env = Environment("conf.yaml")
target = env.get_target()
ssh = target.get_driver("SSHDriver")
out, _, code = ssh.run("ps -p $PPID")
print(code)
print(out)
