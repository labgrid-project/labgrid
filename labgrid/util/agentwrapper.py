import base64
import hashlib
import json
import os.path
import subprocess

def b2s(b):
    return base64.b85encode(b).decode('ascii')

def s2b(s):
    return base64.b85decode(s.encode('ascii'))

class AgentError(Exception):
    pass

class AgentException(Exception):
    pass

class AgentWrapper:
    class Proxy:
        def __init__(self, wrapper, name):
            self.wrapper = wrapper
            self.name = name

        def __call__(self, *args, **kwargs):
            return self.wrapper.call(self.name, *args, **kwargs)

    def __init__(self, host):
        agent = os.path.join(
            os.path.abspath(os.path.dirname(__file__)),
            'agent.py')
        agent_data = open(agent, 'rb').read()
        agent_hash = hashlib.sha256(agent_data).hexdigest()
        agent_remote = '.labgrid_agent_{}.py'.format(agent_hash)
        ssh_opts = 'ssh -x -o ConnectTimeout=5 -o PasswordAuthentication=no'.split()
        subprocess.check_call(
            ['rsync', '-e', ' '.join(ssh_opts), '-tq', agent, '{}:{}'.format(host, agent_remote)],
        )
        self.agent = subprocess.Popen(
            ssh_opts + [host, '--', 'python3', agent_remote],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE)

    def __del__(self):
        self.close()

    def __getattr__(self, name):
        return self.Proxy(self, name)

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
            self.agent.wait()
            self.agent = None
            raise AgentException(response['exception'])
        else:
            self.agent.wait()
            self.agent = None
            raise AgentError(response['error'])

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

