from flask import Flask
from flask import request
from flask import send_file
import pandas as pd
from pathlib import Path
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import sys
from influx_connector.influx_connector import InfluxConnector
from riot_connector.riot_connector import RIoTConnector
import math
import logging
import os
from argparse import ArgumentParser

app = Flask(__name__)
riot_connector = None
influx_connector = None
logger = None
PATH = os.path.abspath(os.path.dirname(__file__))


# Declaration of the task as a function.
def check_new_data(*args):
    tags = ['dst', 'dstp', 'service', 'src', 'srcp', 'url']
    riot_connector = args[0]
    influx_connector = args[1]

    for tag in tags:
        path = PATH+'/dataset/lists/' + tag        
        df = pd.read_csv(path + '.csv', header=0)
        l = df['_value'].tolist()
        q = 'import "influxdata/influxdb/schema"\
            schema.tagValues(\
            bucket:"' + influx_connector.get_bucket() + '",\
            tag: "' + tag + '",\
            start: -' + str(riot_connector.get_frequency()) + 'h)'
        org = influx_connector.get_org()
        query_api = influx_connector.get_influxdb_connection()
        try:
            result = query_api.query(org=org, query=q)
        except Exception as err:
            logger.exception(err)
            return
        else:
            results = []
            for table in result:
                for record in table.records:
                    results.append((record.get_value()))
            diffs = list(set(results) - set(l))
            if len(diffs) != 0:
                for diff in diffs:
                    new_row = {'_value': diff}
                    df = df.append(new_row, ignore_index=True)
            df.to_csv(path + '.csv', index=False)


def is_anomaly(value,mean,std,tolerance):
    if float(std) == 0:
        return 0
    else:
        zscore = (value - mean) / std
        if zscore > tolerance:
            return 1
        else:
            return 0


def check_new_hash(hash_table,diff_hash):
    if hash_table in diff_hash:
        return 1
    else:
        return 0


def update_stats_dict(stats_dict,df):
    actual_hash = list(stats_dict.keys())
    new_hash = df['hash_table'].unique().tolist()
    diff_hash = list(set(new_hash) - set(actual_hash))
    stats = pd.DataFrame()
    stats['avg_diff'] = df.groupby('hash_table')['_value_diff'].mean()
    stats['std_diff'] = df.groupby('hash_table')['_value_diff'].std()
    stats['cnt_diff'] = df.groupby('hash_table')['_value_diff'].size()
    stats['ss_diff'] = df.groupby('hash_table')['_value_diff_squared'].sum()
    stats = stats[stats.index.isin(diff_hash)]
    new_stats_dict = stats.T.to_dict('list')
    stats_dict.update(new_stats_dict)
    df['new_hash'] = df.apply(lambda row: check_new_hash(row['hash_table'],diff_hash),axis=1)
    return stats_dict,df


def check_new_anomalies(*args):
    measurements = ['tdmp_bytes_created', 'tdmp_bytes_total', 'tdmp_packets_created', 'tdmp_packets_total']
    riot_connector = args[0]
    influx_connector = args[1]
    for m in measurements:
        path = PATH+'/dataset/stats/' + m
        stats_dict = pd.read_csv(path + '.csv', header=0).set_index('hash_table').T.to_dict('list')
        q = 'from(bucket: "' + influx_connector.get_bucket() + '")\
          |> range(start: -' + str(riot_connector.get_frequency()) + 'h)\
          |> filter(fn: (r) => r["_measurement"] == "' + m + '")'
        try:
            query_api = influx_connector.get_influxdb_connection()
            result = query_api.query(org=influx_connector.get_org(), query=q)
        except Exception as err:
            logger.exception(err)
            return
        else:
            results = []
            for table in result:
                for record in table.records:
                    results.append([record.values.get("_time"), record.values.get("dst"), record.values.get("dstp"),
                                    record.values.get("proto"), record.values.get("service"), record.values.get("src"),
                                    record.values.get("srcp"), record.values.get("url"), record.get_value()])
            df = pd.DataFrame(results, columns=['_time', 'dst', 'dstp', 'proto', 'service', 'src', 'srcp', 'url', '_value'])
            if df.shape[0] != 0:
                df['_value_diff'] = df['_value'].diff()
                df['_value_diff_squared'] = df['_value_diff'].pow(2)
                df['hash_table'] = df.apply(
                    lambda row: row['dst'] + '_' + row['dstp'] + '_' + row['proto'] + '_' + row['service'] + '_' + row[
                        'src'] + '_' + row['srcp'] + '_' + row['url'], axis=1)
                stats_dict, df = update_stats_dict(stats_dict, df)
                df['anomaly_diff'] = df.apply(lambda row: is_anomaly(row['_value_diff'], stats_dict[row['hash_table']][0],
                                                                    stats_dict[row['hash_table']][1],
                                                                     riot_connector.get_tolerance()), axis=1)
                anomalies = df.loc[df['anomaly_diff'] == 1]
                if anomalies.shape[0] != 0:
                    anomalies_drop = anomalies.drop(['_value_diff_squared', 'new_hash', 'anomaly_diff'], axis=1)
                    anomalies_drop.index.names = ['uuid']
                    anomalies_to_send = anomalies_drop.to_csv(header=None, index=False).strip('\n').split('\n')
                    # sending anomalies to RIoT servers
                    for anomaly in anomalies_to_send:
                        riot_connector.send_anomalies(anomaly)
                    if os.stat(PATH+'/dataset/anomalies/' + m + '.csv').st_size == 0:
                        anomalies_drop.to_csv(PATH+'/dataset/anomalies/' + m + '.csv', index=True)
                    else:
                        existing_anomalies = pd.read_csv(PATH+'/dataset/anomalies/' + m + '.csv').append(
                            anomalies_drop, ignore_index=True)
                        existing_anomalies.to_csv(PATH+'/dataset/anomalies/' + m + '.csv', index=True)
                normalities = df.loc[(df['anomaly_diff'] == 0) & (df['new_hash'] == 0)]
                if normalities.shape[0] != 0:
                    for index, row in normalities.iterrows():
                        stat = stats_dict[row['hash_table']]
                        # avg += (value-avg)/n
                        stat[0] += (row['_value_diff'] - stat[0]) / stat[2]
                        stat[3] += math.pow(row['_value_diff'], 2)
                        stat[2] += 1
                        # std = sqrt((1/(n-1)*(ss-(avg.pow(2)/n))))
                        stat[1] = math.sqrt((1 / (stat[2] - 1)) * (stat[3] - (math.pow(stat[0], 2) / stat[2])))
                        stats_dict[row['hash_table']] = stat
                pd.DataFrame.from_dict(stats_dict, orient='index').reset_index().rename(
                    columns={'index': 'hash_table', 0: 'avg_diff', 1: 'std_diff', 2: 'cnt_diff', 3: 'ss_diff'}).to_csv(
                    path + '.csv', index=False)


def periodic_update(riot_connector, influx_connector):
    # Create the background scheduler
    scheduler = BackgroundScheduler()
    # Create the jobs
    scheduler.add_job(func=check_new_data,
                      trigger="interval",
                      seconds=riot_connector.get_frequency() * 60 * 60,
                      args=(riot_connector, influx_connector))

    scheduler.add_job(func=check_new_anomalies,
                      trigger="interval",
                      seconds=riot_connector.get_frequency() * 60 * 60,
                      args=(riot_connector, influx_connector))

    # Start the scheduler
    scheduler.start()
    # /!\ IMPORTANT /!\ : Shut down the scheduler when exiting the app
    atexit.register(lambda: scheduler.shutdown())


@app.route("/")
def home():
    return send_file('info.txt')


@app.route("/status", methods=['GET'])
def get_status():
    return send_file('status.log')


@app.route("/<measurement>/stats", methods=['GET'])
def get_measurement_stats(measurement):
    path = PATH+'/dataset/stats/'+measurement+'.csv'
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
    path = PATH+'/dataset/stats/'+measurement+'.csv'
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
    path = PATH+'/dataset/lists/'+entity_type+'.csv'
    try:
        abs_path = Path(path).resolve(strict=True)
    except FileNotFoundError:
        return "<p>"+entity_type+": Invalid Entity."
    else:
        data = pd.read_csv(path)
        return data.to_html()


@app.route("/<measurement>/anomalies", methods=['GET'])
def get_measurement_anomalies(measurement):
    path = PATH+'/dataset/anomalies/' + measurement + '.csv'
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
    # define the loggin configuration files
    logging.basicConfig(filename=PATH+'/status.log',
                        format='%(asctime)s %(levelname)s %(name)s %(message)s',
                        level=logging.ERROR)
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

    parser = ArgumentParser()
    parser.add_argument('-uri')
    parser.add_argument('-username')
    parser.add_argument('-base_uri')
    parser.add_argument('-bucket')
    parser.add_argument('-org')
    parser.add_argument('-token')
    parser.add_argument('-url')
    args = parser.parse_args()
    uri = args.uri
    username = args.username
    base_uri = args.base_uri
    bucket = args.bucket
    org = args.org
    token = args.token
    url = args.url

    riot_connector = RIoTConnector(uri, username, base_uri)
    riot_connector.get_config_param()
    influx_connector = InfluxConnector(bucket, org, token, url)
    periodic_update(riot_connector, influx_connector)
    app.run(host='0.0.0.0')
