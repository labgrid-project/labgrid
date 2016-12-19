from remotelab import RemotelabPower

POWER = 'rl'
RL_DEVICE = 'kerlink'

select = {'rl': Remotelab, 'user': UserInput}


class PowerManager:
    def __init__(self):
        "Provides power management for the test device"
        self._power = select['rl']()

    def reboot(self):
        self._power.reboot()

    def on(self):
        self._power.on()

    def off(self):
        self._power.off()


class UserInput:
    def __init__(self):
        pass

    def on(self):
        print("Please turn the device on and press enter")
        input()

    def off(self):
        print("Please turn the device off and press enter")
        input()

    def off(self):
        print("Please reboot the device and press enter")
        input()
