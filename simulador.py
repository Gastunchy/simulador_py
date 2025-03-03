import os
import json
from flask import Flask, render_template, request, jsonify
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone
import random
import string
from google.oauth2 import service_account

app = Flask(__name__)

# Cargar configuración desde una variable de entorno en formato JSON
config_json = os.getenv("CONFIG_JSON")

if not config_json:
    raise ValueError("La variable de entorno CONFIG_JSON no está definida.")

# Convertir la cadena JSON a un diccionario
config = json.loads(config_json)

# Extraer las variables desde el JSON
PROJECT_ID = config.get("PROJECT_ID")
TOPIC_VIAJE = config.get("TOPIC_VIAJE")
TOPIC_TELEMETRIA = config.get("TOPIC_TELEMETRIA")
SERVICE_ACCOUNT_KEY = config.get("SERVICE_ACCOUNT_KEY")  # El JSON de credenciales

# Validar que todas las variables necesarias están presentes
if not all([PROJECT_ID, TOPIC_VIAJE, TOPIC_TELEMETRIA, SERVICE_ACCOUNT_KEY]):
    raise ValueError("Faltan valores en CONFIG_JSON. Verifica que todas las claves estén presentes.")

# Convertir SERVICE_ACCOUNT_KEY de string JSON a diccionario
SERVICE_ACCOUNT_KEY = json.loads(config.get("SERVICE_ACCOUNT_KEY"))

# Crear credenciales de servicio correctamente
credentials = service_account.Credentials.from_service_account_info(SERVICE_ACCOUNT_KEY)

# Almacenamiento en memoria para viajes activos
active_trips = {}

# Función para generar un dominio aleatorio
def generate_random_domain():
    length = 6  # Longitud del dominio
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Función para publicar mensajes en Pub/Sub
def publish_message(topic_name, message):
    try:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        print(f"Enviando mensaje a {topic_name}")  # Log antes de publicar
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()  # Esperar a que se publique
        print(f"Mensaje publicado en {topic_name}")  # Log después de publicar
        return True
    except Exception as e:
        print(f"Error al publicar mensaje en {topic_name}: {str(e)}")
        return False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/start_trip", methods=["POST"])
def start_trip():
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
    
    success = publish_message(TOPIC_VIAJE, trip_message)
    
    if success:
        telemetry_thread = threading.Thread(target=simulate_telemetry, args=(trip_id, dominio_aleatorio), daemon=True)
        telemetry_thread.start()
        
        return jsonify({"status": "viaje iniciado", "dominio": dominio_aleatorio, "id_viaje": trip_id})
    else:
        return jsonify({"status": "error", "message": "Error al publicar mensaje de viaje"}), 500

@app.route("/trip_status/<trip_id>", methods=["GET"])
def trip_status(trip_id):
    if trip_id in active_trips:
        return jsonify({"status": "active", "trip_info": active_trips[trip_id]})
    else:
        return jsonify({"status": "not_found"}), 404

@app.route("/telemetry/<trip_id>", methods=["GET"])
def get_telemetry(trip_id):
    if trip_id in active_trips:
        return jsonify({"status": "success", "telemetry": active_trips[trip_id]["telemetry_events"]})
    else:
        return jsonify({"status": "not_found"}), 404

def simulate_telemetry(trip_id, dominio):
    base_lat = 47.4076
    base_long = -8.5531
    
    route = []
    for i in range(10):
        lat = base_lat + (i * 0.002) + random.uniform(-0.0005, 0.0005)
        long = base_long + (i * 0.003) + random.uniform(-0.0005, 0.0005)
        route.append((lat, long))
    
    for i, (lat, long) in enumerate(route):
        evento_code = random.randint(70, 90)
        
        telemetry_message = {
            "uuid": str(uuid.uuid4()),
            "msgDateTime": datetime.now(timezone.utc).isoformat(),
            "messageType": "evento",
            "deviceID": dominio,
            "deviceVendor": "Integra",
            "deviceType": "emulated",
            "gps": {
                "lat": str(lat),
                "long": str(long)
            },
            "eventos": [evento_code]
        }
        
        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "position": {"lat": lat, "long": long},
                "events": [evento_code]
            })
        else:
            print(f"El viaje {trip_id} ya no existe, deteniendo simulación de telemetría")
            break
        
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"Mensaje de telemetría enviado para dominio {dominio}, posición {lat}, {long}")
        
        time.sleep(random.uniform(4.0, 6.0))
    
    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = datetime.now(timezone.utc).isoformat()
        print(f"Viaje {trip_id} completado")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    debug_mode = os.getenv("FLASK_ENV") == "development"
    
    print(f"Iniciando aplicación Flask en el puerto {port}")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
