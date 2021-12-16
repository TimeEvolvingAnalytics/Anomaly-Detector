from flask import Flask
from flask import request
import pandas as pd
import json
from pathlib import Path

app = Flask(__name__)

_STATUS = 200

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
    app.run()
