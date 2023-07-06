#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Add HTTP-JSON-API functions for labgrid-netio power driver.
Set model in YML-CFG to 'netio_json'.
"""
__author__ = "Eugen Wiens, Christian Happ, Raffael Krakau"
__copyright__ = "Copyright 2023, JUMO GmbH & Co. KG"
__email__ = "Eugen.Wiens@jumo.net, Christian.Happ@jumo.net"
__date__ = "2023-07-05"
__status__ = "Production"

import json

import requests

PORT = 80


class __NetioControl:
    """
    Netio-Class to switch sockets via HTTP-JSON-API
    """
    __host: str
    __port: int
    __username: str
    __password: str

    def __init__(self, host, port=80, username="", password=""):
        self.__host = host
        self.__port = port
        self.__username = username
        self.__password = password

    def set_state(self, socketID, action):
        """
        Set power state by socket port number (e.g. 1 - 8) and an action ('1'-'4').

        - actions:
            - 0: Turn OFF,
            - 1: Turn ON,
            - 2: Short OFF delay (restart),
            - 3: Short ON delay,
            - 4: Toggle (invert the state)
        """
        state = None
        response = requests.post(self.generate_request_url(), json=self.get_request_json_data(socketID, action))

        if response.ok:
            responseDict = json.loads(response.text)
            outputStates = responseDict['Outputs']

            for outputState in outputStates:
                if outputState['ID'] == socketID:
                    state = outputState
                    break
        else:
            raise Exception(f"Cannot SET the power state for socket number: {socketID} for action: {action}."
                            f" Error code: {response.text}")

        return state

    def get_state(self, socketID):
        """
        Get current state of a given socket number as json.
        """
        state = None
        response = requests.get(self.generate_request_url())

        if response.ok:
            responseDict = json.loads(response.text)

            for outputState in responseDict['Outputs']:
                if outputState['ID'] == socketID:
                    state = outputState['State']
                    break
        else:
            raise Exception(f"Cannot get the power state for socket {socketID}. Error code: {response.text}")

        return state

    def convert_socket_id(self, socketID) -> int:
        """
        Cast socketID to int.

        raises ValueError
        """
        try:
            socketID = int(socketID)
        except ValueError as e:
            raise Exception(f"socketID \"{socketID}\" could not be converted to an integer: {e}!")

        return socketID

    def generate_request_url(self) -> str:
        """
        Generate request URL from given params.
        """
        requestUrl = 'http://'

        if self.__username and self.__password:
            requestUrl += f'{self.__username}:{self.__password}@'

        requestUrl += f'{self.__host}:{self.__port}/netio.json'

        return requestUrl

    def get_request_json_data(self, socketID, action) -> str:
        data = f'{{"Outputs":[{{"ID":{socketID},"Action":{self.convert_action(action)}}}]}}'
        return json.loads(data)

    def to_str(self, toConvert) -> str:
        if toConvert == 1 or toConvert is True:
            toConvert = "1"
        elif toConvert == 0 or toConvert is False:
            toConvert = "0"
        return toConvert

    def convert_action(self, action) -> str:
        action = self.to_str(action)

        try:
            assert 0 <= int(action) <= 4
            return action
        except AssertionError as ae:
            raise Exception(f"{ae}\n Action \"{action}\" seems not right, should be between -> '0'-'4'!")


def power_set(host, port, index, action):
    """
    Set netio-state at index(socketID)

    - host: netio-device adress
    - port: standard is 80
    - index: depends on netio-device 1-n (n is the size of netio)
    - action:
        - 0: Turn OFF,
        - 1: Turn ON,
        - 2: Short OFF delay (restart),
        - 3: Short ON delay,
        - 4: Toggle (invert the state)
    """
    netio = __NetioControl(host, port)
    print(netio.set_state(netio.convert_socket_id(index), action))


def power_get(host, port, index):
    """
    Get power-state as json

    - host: netio-device adress
    - port: standard is 80
    - index: depends on netio-device 1-n (n is the size of netio)
    """
    netio = __NetioControl(host, port)
    return netio.get_state(netio.convert_socket_id(index))
