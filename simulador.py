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
PROJECT_ID = "crypto-avatar-452213-k0"
TOPIC_VIAJE = "viaje-topic"
TOPIC_TELEMETRIA = "telemetria-topic"
publisher = pubsub_v1.PublisherClient()

def publish_message(topic_name, message):
    try:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        print(f"Enviando mensaje a {topic_name}")  # Log antes de publicar
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()  # Esperar a que se publique
        print(f"Mensaje publicado en {topic_name}")  # Log después de publicar
    except Exception as e:
        print(f"Error al publicar mensaje en {topic_name}: {str(e)}")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/favicon.ico")
def favicon():
    return '', 204  # Responde con un estado 204 (No Content) para evitar el error 404

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
    
    # Iniciar un hilo para la simulación de telemetría
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
        print(f"Publicando telemetría para {dominio}")  # Log antes de enviar
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"Mensaje de telemetría enviado para dominio {dominio}")  # Log después de enviar
        time.sleep(5)  # Esperar 5 segundos entre mensajes

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
