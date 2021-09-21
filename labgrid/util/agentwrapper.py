import base64
import hashlib
import json
import os.path
import subprocess
import traceback
import logging

def b2s(b):
    return base64.b85encode(b).decode('ascii')

def s2b(s):
    return base64.b85decode(s.encode('ascii'))

class AgentError(Exception):
    pass

class AgentException(Exception):
    pass

class MethodProxy:
    def __init__(self, wrapper, name):
        self.wrapper = wrapper
        self.name = name

    def __call__(self, *args, **kwargs):
        return self.wrapper.call(self.name, *args, **kwargs)

class ModuleProxy:
    def __init__(self, wrapper, name):
        self.wrapper = wrapper
        self.name = name

    def __getattr__(self, name):
        return MethodProxy(self.wrapper, f'{self.name}.{name}')

class AgentWrapper:

    def __init__(self, host=None):
        self.agent = None
        self.loaded = {}
        self.logger = logging.getLogger(f"ResourceExport({host})")

        agent = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'agent.py')
        if host:
            # copy agent.py and run via ssh
            agent_data = open(agent, 'rb').read()
            agent_hash = hashlib.sha256(agent_data).hexdigest()
            agent_remote = f'.labgrid_agent_{agent_hash}.py'
            ssh_opts = 'ssh -x -o ConnectTimeout=5 -o PasswordAuthentication=no'.split()
            subprocess.check_call(
                ['rsync', '-e', ' '.join(ssh_opts), '-tq', agent,
                 f'{host}:{agent_remote}'],
            )
            self.agent = subprocess.Popen(
                ssh_opts + [host, '--', 'python3', agent_remote],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)
        else:
            # run locally
            self.agent = subprocess.Popen(
                ['python3', agent],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE)

    def __del__(self):
        self.close()

    def __getattr__(self, name):
        return MethodProxy(self, name)

    def call(self, method, *args, **kwargs):
        request = {
            'method': method,
            'args': args,
            'kwargs': kwargs,
            }
        request = json.dumps(request)
        request = request.encode('ASCII')
        self.agent.stdin.write(request+b'\n')
        self.agent.stdin.flush()
        response = self.agent.stdout.readline()
        response = response.decode('ASCII')
        response = json.loads(response)
        if 'result' in response:
            return response['result']
        elif 'exception' in response:
            e = response['exception']
            # work around BaseException repr change
            # https://bugs.python.org/issue30399
            if e[-2:] == ',)':
                e = e[:-2] + ')'
            self.logger.debug("Traceback from agent (most recent call last) for %s:", e)
            for line in ''.join(traceback.format_list(response['tb'])).splitlines():
                self.logger.debug(line)
            raise AgentException(e)
        elif 'error' in response:
            self.agent.wait()
            self.agent = None
            raise AgentError(response['error'])

        raise AgentError(f"unknown response from agent: {response}")

    def load(self, name):
        if name in self.loaded:
            return self.loaded[name]

        filename = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'agents', f'{name}.py')
        source = open(filename, 'r').read()

        self.call('load', name, source)

        proxy = ModuleProxy(self, name)
        self.loaded[name] = proxy
        return proxy

    def close(self):
        if self.agent is None:
            return
        request = {
            'close': True,
            }
        request = json.dumps(request)
        request = request.encode('ASCII')
        self.agent.stdin.write(request+b'\n')
        self.agent.stdin.flush()
        self.agent.wait()
        self.agent = None
