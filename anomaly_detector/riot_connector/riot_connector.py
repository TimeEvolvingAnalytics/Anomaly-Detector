import hashlib
import requests
import time
import random
import logging


class RioTConnector:
    """
    Connection to RioT server
    """
    #method = 'GET'
    #uri = '/global'  # use '/global' to access the variables, '/auth' only for the authentication
    #username = 'service'
    #BASE_URI = 'https://demo.riotsecure.io:6443'

    def __init__(self, uri, username, base_uri):
        self._uri = uri
        self._username = username
        self._base_uri = base_uri
        self._tolerance = 3
        self._frequency = 24

    def get_frequency(self):
        return self._frequency

    def get_tolerance(self):
        return self._tolerance

    def create_auth(self, method):
        hash1 = '7CC384C2A10CEA62FB2A37CFDA222C04'

        now = '{:8X}'.format(int(time.time()))
        POOL = "ABCDEF0123456789"
        nonce_list = []
        for i in range(0, 24):
            nonce_list.append(POOL[random.randint(0, len(POOL) - 1)])
        nonce_str = ''.join(nonce_list)
        nonce = now + nonce_str

        auth2 = method + ':' + self._uri
        hash_object = hashlib.md5(auth2.encode())
        hash2 = hash_object.hexdigest().upper()

        auth3 = hash1 + ':' + nonce + ':' + hash2
        hash_object = hashlib.md5(auth3.encode())
        authority = hash_object.hexdigest().upper()

        return "oasis username=\"" + self._username + "\", nonce=\"" + nonce + "\", authority=\"" + authority + "\""

    def _update_values(self, tol, freq):
        if 2 <= tol <= 6:
            self._tolerance = tol
        else:
            self._tolerance = 3
        if 1 <= freq <= 168:
            self._frequency = freq
        else:
            self._frequency = 24

    def get_config_param(self):
        headers = {
            'Authorization': self.create_auth('GET'),
            'Content-Type': "application/json",
            'Cache-Control': "no-cache"
        }
        _uri = self._uri + "?expand"
        response = requests.get(self._base_uri + _uri, headers=headers)

        log = logging.getLogger('__main__')

        if response.status_code == 200:
            tol = response.json()['keys']['net_anomoly']['tolerance']
            freq = response.json()['keys']['net_anomoly']['frequency']
            self._update_values(tol, freq)
        elif response.status_code == 404:
            log.error('Get configuration parameters: Error 404 in connecting to RioT server')
        elif response.status_code == 401:
            log.error('Get configuration parameters: Error 401: Unauthorized access in connecting to RioT server')
        return self._tolerance, self._frequency

    def send_anomalies(self, anomaly):
        headers = {
            'Authorization': self.create_auth('PUT'),
            'Content-Type': "application/json",
            'Cache-Control': "no-cache",
            "Service": "net-anomoly",
            "Level": "WARN",
            "Message": "Traffic anomaly detected, DATA: " + anomaly
        }
        _uri = self._uri + "s/events?expand"
        response = requests.put(self._base_uri + _uri, headers=headers)

        log = logging.getLogger('__main__')

        if response.status_code == 404:
            log.error('Sending anomalies: Error 404 in connecting to RioT server')
        elif response.status_code == 401:
            log.error('Sending anomalies: Error 401: Unauthorized access in connecting to RioT server')
        return
