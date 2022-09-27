#!/usr/bin/env python3

import json
import os
import signal
import sys
import base64
import types

def b2s(b):
    return base64.b85encode(b).decode('ascii')

def s2b(s):
    return base64.b85decode(s.encode('ascii'))

class Agent:
    def __init__(self):
        self.methods = {}
        self.register('load', self.load)
        self.register('list', self.list)

        # use real stdin/stdout
        self.stdin = sys.stdin
        self.stdout = sys.stdout

        # use stderr for normal prints
        sys.stdout = sys.stderr

    def send(self, data):
        self.stdout.write(json.dumps(data)+'\n')
        self.stdout.flush()

    def register(self, name, func):
        assert name not in self.methods
        self.methods[name] = func

    def load(self, name, source):
        module = types.ModuleType(name)
        exec(compile(source, f'<loaded {name}>', 'exec'), module.__dict__)
        for k, v in module.methods.items():  # pylint: disable=no-member
            self.register(f'{name}.{k}', v)

    def list(self):
        return list(self.methods.keys())

    def run(self):
        for line in self.stdin:
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self.send({'error': f'request parsing failed for {repr(line)}'})
                break

            if request.get('close', False):
                break

            name = request['method']
            args = request['args']
            kwargs = request['kwargs']
            try:
                response = self.methods[name](*args, **kwargs)
                self.send({'result': response})
            except Exception as e:  # pylint: disable=broad-except
                import traceback
                try:
                    tb = [list(x) for x in traceback.extract_tb(sys.exc_info()[2])]
                except:
                    tb = None
                self.send({'exception': repr(e), 'tb': tb})

def handle_test(*args, **kwargs):  # pylint: disable=unused-argument
    return args[::-1]

def handle_error(message):
    raise ValueError(message)

def handle_usbtmc(index, cmd, read=False):
    assert isinstance(index, int)
    cmd = s2b(cmd)
    fd = os.open(f'/dev/usbtmc{index}', os.O_RDWR)
    os.write(fd, cmd)
    if not read:
        os.close(fd)
        return None
    data = []
    while True:
        data.append(os.read(fd, 4096))
        if len(data[-1]) < 4096:
            break
    os.close(fd)
    return b2s(b''.join(data))

def main():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    a = Agent()
    a.register('test', handle_test)
    a.register('error', handle_error)
    a.register('usbtmc', handle_usbtmc)
    a.run()

if __name__ == "__main__":
    main()
