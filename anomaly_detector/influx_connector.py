import influxdb_client


class InfluxConnector:
    """
    Connection to influxdb
    """
    def __init__(self, bucket, org, token, url):
        self._bucket = bucket
        self._org = org
        self._token = token
        self._url = url

    def set_bucket(self, new_bucket):
        self._bucket = new_bucket

    def get_org(self):
        return self._org

    def set_org(self, new_org):
        self._org = new_org

    def set_token(self, new_token):
        self._token = new_token

    def set_url(self, new_url):
        self._url = new_url

    def get_influxdb_connection(self):
        client = influxdb_client.InfluxDBClient(
            url=self._url,
            token=self._token,
            org=self._token
        )
        return client.query_api()
