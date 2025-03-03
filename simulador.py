from flask import Flask, render_template, request, jsonify
import json
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone
import random
import string
from google.cloud import secretmanager

app = Flask(__name__)

# Función para cargar secretos de Google Secret Manager
def load_secret():
    client = secretmanager.SecretManagerServiceClient()
    secret_name = "projects/488709866434/secrets/simulador_secret/versions/latest"

    try:
        response = client.access_secret_version(request={"name": secret_name})
        secret_data = response.payload.data.decode("UTF-8")
        return json.loads(secret_data)  # Retorna como diccionario
    except Exception as e:
        print(f"Error al cargar secreto: {str(e)}")
        return {}  # Retorna un diccionario vacío si falla

# Cargar los secretos
secreto = load_secret()

# Verificar si los secretos se cargaron correctamente
if not secreto:
    raise ValueError("Error: No se pudo cargar el secreto desde Secret Manager.")

PROJECT_ID = secreto.get("PROJECT_ID")
TOPIC_VIAJE = secreto.get("TOPIC_VIAJE")
TOPIC_TELEMETRIA = secreto.get("TOPIC_TELEMETRIA")

if not PROJECT_ID or not TOPIC_VIAJE or not TOPIC_TELEMETRIA:
    raise ValueError("Error: Faltan configuraciones en el secreto. Verifica PROJECT_ID y los nombres de los topics.")

# Inicializar cliente de Pub/Sub
publisher = pubsub_v1.PublisherClient()

# Diccionario para almacenar los viajes activos
active_trips = {}

# Función para generar un dominio aleatorio
def generate_random_domain():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# Función para publicar mensajes en Pub/Sub
def publish_message(topic_name, message):
    if not PROJECT_ID or not topic_name:
        print("Error: PROJECT_ID o topic_name están vacíos.")
        return False

    try:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        print(f"📤 Enviando mensaje a {topic_name} en {topic_path}")

        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()  # Esperar confirmación de publicación
        print(f"✅ Mensaje publicado en {topic_name}")
        return True
    except Exception as e:
        print(f"❌ Error al publicar en {topic_name}: {str(e)}")
        return False

# Ruta principal
@app.route("/")
def index():
    return render_template("index.html")

# Ruta para evitar error 404 del favicon
@app.route("/favicon.ico")
def favicon():
    return '', 204

# Ruta para iniciar un viaje
@app.route("/start_trip", methods=["POST"])
def start_trip():
    data = request.json
    if not data:
        return jsonify({"status": "error", "message": "Solicitud vacía"}), 400

    required_fields = ["tipoViaje", "idSucursalOrigen", "idSucursalDestino", "hr", "transportista", "dominioSemi", "precintos"]
    for field in required_fields:
        if field not in data:
            return jsonify({"status": "error", "message": f"Falta el campo requerido: {field}"}), 400

    trip_id = str(uuid.uuid4())
    dominio_aleatorio = generate_random_domain()

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
        "telemetry_events": []
    }

    success = publish_message(TOPIC_VIAJE, trip_message)

    if success:
        threading.Thread(target=simulate_telemetry, args=(trip_id, dominio_aleatorio), daemon=True).start()
        return jsonify({"status": "viaje iniciado", "dominio": dominio_aleatorio, "id_viaje": trip_id})
    else:
        return jsonify({"status": "error", "message": "Error al publicar el mensaje de viaje"}), 500

# Ruta para obtener el estado de un viaje
@app.route("/trip_status/<trip_id>", methods=["GET"])
def trip_status(trip_id):
    trip = active_trips.get(trip_id)
    if trip:
        return jsonify({"status": "active", "trip_info": trip})
    return jsonify({"status": "not_found"}), 404

# Ruta para obtener los eventos de telemetría de un viaje
@app.route("/telemetry/<trip_id>", methods=["GET"])
def get_telemetry(trip_id):
    trip = active_trips.get(trip_id)
    if trip:
        return jsonify({"status": "success", "telemetry": trip["telemetry_events"]})
    return jsonify({"status": "not_found"}), 404

# Simulación de telemetría
def simulate_telemetry(trip_id, dominio):
    base_lat, base_long = 47.4076, -8.5531

    route = [(base_lat + i * 0.002 + random.uniform(-0.0005, 0.0005),
              base_long + i * 0.003 + random.uniform(-0.0005, 0.0005))
             for i in range(10)]

    for lat, long in route:
        evento_code = random.randint(70, 90)

        telemetry_message = {
            "uuid": str(uuid.uuid4()),
            "msgDateTime": datetime.now(timezone.utc).isoformat(),
            "messageType": "evento",
            "deviceID": dominio,
            "deviceVendor": "Integra",
            "deviceType": "emulated",
            "gps": {"lat": str(lat), "long": str(long)},
            "eventos": [evento_code]
        }

        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "position": {"lat": lat, "long": long},
                "events": [evento_code]
            })

        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"📡 Telemetría enviada: {dominio}, Posición: {lat}, {long}")

        time.sleep(random.uniform(4.0, 6.0))

    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = datetime.now(timezone.utc).isoformat()

# Iniciar servidor Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)