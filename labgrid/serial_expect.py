from pexpect import fdpexpect
import serial
import logging

SERIAL_PORT = '/dev/ttyUSB1'
PASSWORD = 'password'
PROMPT = "root@linux:~#"

class SerialExpect(object):
    def __init__(self):
        self.serial = serial.Serial(SERIAL_PORT, 115200)
        self.expect = fdpexpect.fdspawn(self.serial,logfile=open('expect.log','bw'))
        self.password = PASSWORD
        self.prompt = PROMPT
        self.logger = logging.getLogger('SerialExpect')
        self.login()

    def login(self):
        self.expect.sendline("")
        self.expect.expect(".* login: ")
        self.expect.sendline("root")
        self.expect.expect("Password: ")
        self.expect.sendline(self.password)
        self.expect.expect(self.prompt)

    def get_ip(self):
        self.expect.sendline("ip -o -4 addr show dev eth0 | cut -d ' ' -f 7 | cut -f 1 -d '/'")
        self.expect.expect(self.prompt)
        return self.expect.before.split(b"\r\n")[-2].decode('utf-8')

    def __del__(self):
        self.expect.sendline('exit')
