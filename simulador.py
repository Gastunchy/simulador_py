import os
import json
from flask import Flask, render_template, request, jsonify
import uuid
import time
import threading
from google.cloud import pubsub_v1, secretmanager
from datetime import datetime, timezone
import random
import string
from google.oauth2 import service_account

app = Flask(__name__)

# Configuración

def get_secret(secret_name):
    """Obtiene el valor de un secreto desde Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    secret_path = f"projects/488709866434/secrets/simulador_secret/versions/latest"
    
    response = client.access_secret_version(name=secret_path)
    return response.payload.data.decode("UTF-8")

# Obtener configuración desde Secret Manager
config_json = get_secret(SECRET_NAME)
config = json.loads(config_json)  # Convertir de string JSON a diccionario

# Extraer valores de configuración
TOPIC_VIAJE = config["TOPIC_VIAJE"]
TOPIC_TELEMETRIA = config["TOPIC_TELEMETRIA"]

# Convertir SERVICE_ACCOUNT_KEY de string JSON a diccionario si es necesario
if isinstance(config["SERVICE_ACCOUNT_KEY"], str):
    SERVICE_ACCOUNT_KEY = json.loads(config["SERVICE_ACCOUNT_KEY"])
else:
    SERVICE_ACCOUNT_KEY = config["SERVICE_ACCOUNT_KEY"]

# Crear credenciales desde Secret Manager
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_KEY)

# Crear el cliente de Pub/Sub con las credenciales
publisher = pubsub_v1.PublisherClient(credentials=credentials)

def generate_random_id():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def publish_message(topic_name, message):
    topic_path = publisher.topic_path(PROJECT_ID, topic_name)
    future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
    return future.result()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/iniciar_viaje', methods=['POST'])
def iniciar_viaje():
    viaje_id = generate_random_id()
    inicio = datetime.now(timezone.utc).isoformat()
    mensaje = {"viaje_id": viaje_id, "inicio": inicio}
    publish_message(TOPIC_VIAJE, mensaje)
    return jsonify({"status": "Viaje iniciado", "viaje_id": viaje_id})

@app.route('/enviar_telemetria', methods=['POST'])
def enviar_telemetria():
    data = request.json
    publish_message(TOPIC_TELEMETRIA, data)
    return jsonify({"status": "Telemetría enviada"})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
