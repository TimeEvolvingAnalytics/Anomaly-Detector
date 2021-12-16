from flask import Flask
from flask import request

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/status", methods=['GET'])
def get_status():
    return 200


@app.route("/<measurement>/stats", methods=['GET'])
def get_measurement_stats(measurement):
    # dataset/stats/<measurement>.csv
    # colonna hash + campi che compongono l'hash (split per _)
    return 200


@app.route("/<measurement>/stats/<hash>", methods=['GET'])
def get_measurement_stats_hash(measurement, hash):
    # dataset/stats/<measurement>.csv
    # ritorno le statistiche corrispondenti all'hash
    return 200


@app.route("/<entity_type>", methods=['GET'])
def get_entity_type(entity_type):
    # dataset/lists/<entity_type>.csv
    # ritorno il dataset, se non c'è ritorno errore
    return 200


@app.route("/<measurement>/anomalies", methods=['GET'])
def get_measurement_anomalies(measurement):
    # dataset/anomalies/<measurement>.csv
    # ritorno il dataset, se non c'è ritorno errore
    return 200


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
