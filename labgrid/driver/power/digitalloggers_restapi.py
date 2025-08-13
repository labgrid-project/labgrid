'''
Driver for Digital Loggers PDU that use the REST API.
Tested with Ethernet Power Controller 7.

Based on https://www.digital-loggers.com/restapi.pdf

By default, only an authenticated user is allowed by REST API.

NetworkPowerPort:
    model: 'digitalloggers_restapi'
    host: 'http://admin:1234@192.168.0.100'
    index: 0
'''
from urllib.parse import urlparse

import requests
from requests.auth import HTTPDigestAuth
from requests.packages import urllib3


def extract_user_password_from_host(host):
    url = urlparse(host)
    if '@' in url.netloc:
        user=url.username
        password=url.password
        _host= f'{url.scheme}://{url.netloc.split("@")[1]}'
    else:
        user = None
        password = None
        _host= f'{url.scheme}://{url.netloc}'
    return user, password, _host

def power_set(host, port, index, value):
    # curl -u admin:1234 -v -X PUT -H "X-CSRF: x" --data 'value=true' --digest http://192.168.0.100/restapi/relay/outlets/=0/state/
    # curl -u admin:1234 -v -X PUT -H "X-CSRF: x" --data 'value=false' --digest http://192.168.0.100/restapi/relay/outlets/=0/state/
    # curl --insecure -u admin:1234 -v -X PUT -H "X-CSRF: x" --data 'value=true' --digest https://192.168.0.100/restapi/relay/outlets/=0/state/
    # curl --insecure -u admin:1234 -v -X PUT -H "X-CSRF: x" --data 'value=false' --digest https://192.168.0.100/restapi/relay/outlets/=0/state/
    assert port is None

    index = int(index)
    value = 'true' if value else 'false'
    payload = {'value' : value }
    headers = {'X-CSRF': 'x', 'Accept': 'application/json'}
    user, password, url = extract_user_password_from_host(host)
    host = f'{url}/restapi/relay/outlets/={index}/state/'
    with urllib3.warnings.catch_warnings():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if user and password:
            r = requests.put(host, data=payload, auth=HTTPDigestAuth(user, password), headers=headers, verify=False)
        else:
            r = requests.put(host, data=payload, headers=headers, verify=False)
        r.raise_for_status()

def power_get(host, port, index):
    # curl -u admin:1234 -v -X GET -H "X-CSRF: x" --digest http://192.168.0.100/restapi/relay/outlets/=0/state/
    # curl --insecure -u admin:1234 -v -X GET -H "X-CSRF: x" --digest https://192.168.0.100/restapi/relay/outlets/=0/state/
    assert port is None

    index = int(index)
    user, password, url = extract_user_password_from_host(host)
    headers = {'X-CSRF': 'x', 'Accept': 'application/json'}
    host = f'{url}/restapi/relay/outlets/={index}/state/'
    with urllib3.warnings.catch_warnings():
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        if user and password:
            r = requests.get(host, auth=HTTPDigestAuth(user, password), headers=headers, verify=False)
        else:
            r = requests.get(host, headers=headers, verify=False)
        r.raise_for_status()
    statuses = r.json()
    return statuses[0]
