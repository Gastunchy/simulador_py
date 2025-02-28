from flask import Flask, render_template, request, jsonify
import json
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone
import random

app = Flask(__name__)

# Configuración de Pub/Sub
PROJECT_ID = "tu-proyecto"
TOPIC_VIAJE = "viaje-topic"
TOPIC_TELEMETRIA = "telemetria-topic"
publisher = pubsub_v1.PublisherClient()

def publish_message(topic_name, message):
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    publisher.publish(topic_path, json.dumps(message).encode("utf-8"))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start_trip", methods=["POST"])
def start_trip():
    data = request.json
    trip_message = {
        "uuid": str(uuid.uuid4()),
        "msgDateTime": datetime.now(timezone.utc).isoformat(),
        "messageType": "novedad",
        "entityType": "viaje",
        "viaje": {
            "tipoViaje": data["tipoViaje"],
            "idSucursalOrigen": data["idSucursalOrigen"],
            "idSucursalDestino": data["idSucursalDestino"],
            "hr": data["hr"],
            "transportista": data["transportista"],
            "dominio": data["dominio"],
            "dominioSemi": data["dominioSemi"],
            "precintos": data["precintos"]
        }
    }
    publish_message(TOPIC_VIAJE, trip_message)
    
    threading.Thread(target=simulate_telemetry, args=(data["dominio"],)).start()
    return jsonify({"status": "viaje iniciado"})

def simulate_telemetry(dominio):
    for _ in range(10):  # Enviar 10 mensajes de telemetría como prueba
        telemetry_message = {
            "uuid": str(uuid.uuid4()),
            "msgDateTime": datetime.now(timezone.utc).isoformat(),
            "messageType": "evento",
            "deviceID": dominio,
            "deviceVendor": "Integra",
            "deviceType": "emulated",
            "gps": {
                "lat": str(47.4076 + random.uniform(-0.01, 0.01)),
                "long": str(-8.5531 + random.uniform(-0.01, 0.01))
            },
            "eventos": [76]
        }
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        time.sleep(5)  # Esperar 5 segundos entre mensajes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)