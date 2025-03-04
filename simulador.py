from dotenv import load_dotenv
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

# Función para acceder y cargar los secretos desde Google Secret Manager
def load_secret(secret_name):
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(name=secret_name)
    secret_data = response.payload.data.decode("UTF-8")
    return json.loads(secret_data)

# Cargar el secreto de credenciales de Google Cloud
sa_secret_name = "projects/488709866434/secrets/SA_data/versions/latest"  # Reemplaza con el nombre de tu secreto
sa_data = load_secret(sa_secret_name)

# Guardar las credenciales de la cuenta de servicio en un archivo temporal
with open("/tmp/google-credentials.json", "w") as f:
    json.dump(sa_data, f)

# Establecer la variable de entorno para las credenciales de Google Cloud
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/tmp/google-credentials.json"

# Cargar el secreto de configuración del proyecto
project_config_secret_name = "projects/YOUR_PROJECT_ID/secrets/Project_config/versions/latest"  # Reemplaza con el nombre de tu secreto
project_config = load_secret(project_config_secret_name)

# Extraer las variables relacionadas con Pub/Sub desde el JSON
PROJECT_ID = project_config.get("PROJECT_ID", "")
TOPIC_VIAJE = project_config.get("TOPIC_VIAJE", "")
TOPIC_TELEMETRIA = project_config.get("TOPIC_TELEMETRIA", "")

# Extraer el puerto y el entorno de Flask
PORT = int(project_config.get("PORT", 8080))
FLASK_ENV = project_config.get("FLASK_ENV", "production")

# Inicialización de la aplicación Flask y cliente de Pub/Sub
app = Flask(__name__)
publisher = pubsub_v1.PublisherClient()

# Almacenamiento en memoria para viajes activos
active_trips = {}

def generate_random_domain():
    """Genera un dominio aleatorio de 6 caracteres"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def publish_message(topic_name, message):
    """Publica un mensaje en el tema de Pub/Sub especificado"""
    try:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()
        return True
    except Exception as e:
        print(f"Error al publicar mensaje en {topic_name}: {str(e)}")
        return False

@app.route("/")
def index():
    """Renderiza la página de inicio"""
    return render_template("index.html")

@app.route("/start_trip", methods=["POST"])
def start_trip():
    """Inicia un nuevo viaje y comienza a simular telemetría"""
    data = request.json
    dominio_aleatorio = generate_random_domain()
    trip_id = str(uuid.uuid4())

    trip_message = {
        "uuid": trip_id,
        "msgDateTime": datetime.now(timezone.utc).isoformat(),
        "messageType": "novedad",
        "entityType": "viaje",
        "viaje": {
            "tipoViaje": data["tipoViaje"],
            "idSucursalOrigen": data["idSucursalOrigen"],
            "idSucursalDestino": data["idSucursalDestino"],
            "hr": data["hr"],
            "transportista": data["transportista"],
            "dominio": dominio_aleatorio,
            "dominioSemi": data["dominioSemi"],
            "precintos": data["precintos"]
        }
    }

    active_trips[trip_id] = {
        "dominio": dominio_aleatorio,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "telemetry_events": [],
        "status": "active"
    }

    if publish_message(TOPIC_VIAJE, trip_message):
        threading.Thread(target=simulate_telemetry, args=(trip_id, dominio_aleatorio), daemon=True).start()
        return jsonify({"status": "viaje iniciado", "dominio": dominio_aleatorio, "id_viaje": trip_id})
    else:
        return jsonify({"status": "error", "message": "Error al publicar mensaje de viaje"}), 500

@app.route("/trip_status/<trip_id>", methods=["GET"])
def trip_status(trip_id):
    """Consulta el estado de un viaje activo"""
    if trip_id in active_trips:
        return jsonify({"status": "active", "trip_info": active_trips[trip_id]})
    else:
        return jsonify({"status": "not_found"}), 404

@app.route("/telemetry/<trip_id>", methods=["GET"])
def get_telemetry(trip_id):
    """Obtiene los eventos de telemetría de un viaje activo"""
    if trip_id in active_trips:
        return jsonify({"status": "success", "telemetry": active_trips[trip_id]["telemetry_events"]})
    else:
        return jsonify({"status": "not_found"}), 404

def simulate_telemetry(trip_id, dominio):
    """Simula eventos de telemetría para un viaje"""
    base_lat, base_long = 47.4076, -8.5531
    route = [(base_lat + i * 0.002, base_long + i * 0.003) for i in range(10)]

    for i, (lat, long) in enumerate(route):
        telemetry_message = {
            "uuid": str(uuid.uuid4()),
            "msgDateTime": datetime.now(timezone.utc).isoformat(),
            "messageType": "evento",
            "deviceID": dominio,
            "deviceVendor": "Integra",
            "deviceType": "emulated",
            "gps": {"lat": str(lat), "long": str(long)},
            "eventos": [random.randint(70, 90)]
        }

        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "position": {"lat": lat, "long": long},
                "events": telemetry_message["eventos"]
            })
        else:
            break

        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        time.sleep(random.uniform(4.0, 6.0))

    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = datetime.now(timezone.utc).isoformat()

if __name__ == "__main__":
    debug_mode = FLASK_ENV == "development"
    app.run(host="0.0.0.0", port=PORT, debug=debug_mode)
