from labgrid.protocol import CommandProtocol


def test_shell(target):
    command = target.get_driver(CommandProtocol)
    print(command.run('ls /'))
