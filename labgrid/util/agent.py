#!/usr/bin/env python3

import json
import os
import sys
import base64

def b2s(b):
    return base64.b85encode(b).decode('ascii')

def s2b(s):
    return base64.b85decode(s.encode('ascii'))

class Agent:
    def __init__(self):
        self.methods = {}

    def _send(self, data):
        sys.stdout.write(json.dumps(data)+'\n')
        sys.stdout.flush()

    def register(self, name, func):
        assert name not in self.methods
        self.methods[name] = func

    def run(self):
        for line in sys.stdin:
            if not line:
                continue

            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._send({'error': 'request parsing failed'})
                break

            if request.get('close', False):
                break

            name = request['method']
            args = request['args']
            kwargs = request['kwargs']
            try:
                response = self.methods[name](*args, **kwargs)
                self._send({'result': response})
            except Exception as e:  # pylint: disable=broad-except
                self._send({'exception': repr(e)})
                break

def handle_test(*args, **kwargs):
    return args[::-1]

def handle_error(message):
    raise RuntimeError(message)

def handle_usbtmc(index, cmd, read=False):
    assert isinstance(index, int)
    cmd = s2b(cmd)
    fd = os.open('/dev/usbtmc{}'.format(index), os.O_RDWR)
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
    a = Agent()
    a.register('test', handle_test)
    a.register('error', handle_error)
    a.register('usbtmc', handle_usbtmc)
    a.run()

if __name__ == "__main__":
    main()
