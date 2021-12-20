from flask import Flask
from flask import request
import pandas as pd
import json
from pathlib import Path
import time
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import sys
from influx_connector import InfluxConnector
from riot_connector import RioTConnector

app = Flask(__name__)
_STATUS = 200
riot_connector = None
influx_connector = None
# TODO bisogna ritornare tutto come json e non come html


# Declaration of the task as a function.
def check_new_data(*args):
    tags = ['dst', 'dstp', 'service', 'src', 'srcp', 'url']
    riot_connector = args[0]
    influx_connector = args[1]

    for tag in tags:
        path = 'anomaly_detector/dataset/lists/' + tag
        df = pd.read_csv(path + '.csv', header=0)
        l = df['_value'].tolist()
        q = 'import "influxdata/influxdb/schema"\
            schema.tagValues(\
            bucket: "riot",\
            tag: "' + tag + '",\
            start: ' + riot_connector.get_frequency() + ')'
        # system.exit(0)
        org = influx_connector.get_org()
        query_api = influx_connector.get_influxdb_connection()
        result = query_api.query(org=org, query=q)
        results = []
        for table in result:
            for record in table.records:
                results.append((record.get_value()))
        diffs = list(set(results) - set(l))
        if len(diffs) != 0:
            # call API
            print('*** New ' + tag + ' ***')
            for diff in diffs:
                # print(diff)
                new_row = {'_value': diff}
                df = df.append(new_row, ignore_index=True)
        df.to_csv(path + '.csv', index=False)


def periodic_update(riot_connector, influx_connector):
    # Create the background scheduler
    scheduler = BackgroundScheduler()
    # Create the job
    scheduler.add_job(func=check_new_data,
                      trigger="interval",
                      seconds=riot_connector.get_frequency(),
                      args=(riot_connector, influx_connector))
    # Start the scheduler
    scheduler.start()
    # /!\ IMPORTANT /!\ : Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/status", methods=['GET'])
def get_status():
    return 'The status of the Anomaly Detector is ' + str(_STATUS)


@app.route("/<measurement>/stats", methods=['GET'])
def get_measurement_stats(measurement):
    path = 'anomaly_detector/dataset/stats/'+measurement+'.csv'
    try:
        abs_path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        return "<p>"+measurement+": Invalid measurement."
    else:
        columns = ['dst','dstp','proto','service','src','srcp','url']
        data = pd.read_csv(path)
        data[columns] = data['hash_table'].str.split('_', expand=True)
        data.drop(columns=['avg_diff','std_diff','cnt_diff','ss_diff'], inplace=True, axis=1)
        # encode hash_table
        data['hash_table'] = data['hash_table'].apply(lambda row: row.encode('utf8').hex())
        return data.to_html()


@app.route("/<measurement>/stats/<hash>", methods=['GET'])
def get_measurement_stats_hash(measurement, hash):
    path = 'anomaly_detector/dataset/stats/'+measurement+'.csv'
    try:
        abs_path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        return "<p>"+measurement+": Invalid measurement."
    else:
        # decode hash_table
        hash_decoded = bytes.fromhex(hash).decode('utf-8')
        data = pd.read_csv(path)
        data = data[data['hash_table']==hash_decoded]
        data['hash_table'] = hash
        return data.to_html()


@app.route("/<entity_type>", methods=['GET'])
def get_entity_type(entity_type):
    path = 'anomaly_detector/dataset/lists/'+entity_type+'.csv'
    try:
        abs_path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        return "<p>"+entity_type+": Invalid Entity."
    else:
        data = pd.read_csv(path)
        return data.to_html()


@app.route("/<measurement>/anomalies", methods=['GET'])
def get_measurement_anomalies(measurement):
    path = 'anomaly_detector/dataset/anomalies/' + measurement + '.csv'
    try:
        abs_path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        return "<p>" + measurement + ": Invalid Entity."
    else:
        data = pd.read_csv(path)
        data['hash_table'] = data['hash_table'].apply(lambda row: row.encode('utf8').hex())
        return data.to_html()


@app.route("/<measurement>/anomalies/<uuid>", methods=['POST'])
def verify_anomalies(measurement, uuid):
    # dataset/anomalies/<measurement>.csv
    # controllo su uuid
    if request.method == 'POST':
        data = request.form
        # azioni su data
        return 200


if __name__ == "__main__":
    config = sys.argv[1:]
    riot_config = config[:3]
    riot_connector = RioTConnector(riot_config[0], riot_config[1], riot_config[2])
    riot_connector.get_config_param()
    connection_config = config[3:7]
    influx_connector = InfluxConnector(connection_config[0], connection_config[1], connection_config[2], connection_config[3])
    periodic_update(riot_connector, influx_connector)
    app.run()
