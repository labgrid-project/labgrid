import pytest
from labgrid.protocol import ConsoleProtocol, CommandProtocol

def test_shell(target):
     console = target.get_driver(ConsoleProtocol)
     command = target.get_driver(CommandProtocol)
     print(command.run('ls /'))
