
class ConsoleProtocol(object):
    def __init__(self, target):
        self.target = target
        self.target.protocols.append(self)

    def run(self):
        pass
