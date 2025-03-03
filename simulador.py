from flask import Flask, render_template, request, jsonify
import json
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone
import random
import string
import os
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

app = Flask(__name__)

# Configuración de Pub/Sub
PROJECT_ID = os.getenv('Project')
TOPIC_VIAJE = os.getenv('viaje_topic')
TOPIC_TELEMETRIA = os.getenv('telemetria_topic')

publisher = pubsub_v1.PublisherClient()

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

# Ruta principal
@app.route("/")
def index():
    return render_template("index.html")

# Ruta para el favicon (para evitar error 404)
@app.route("/favicon.ico")
def favicon():
    return '', 204  # Responde con un estado 204 (No Content) para evitar el error 404

# Ruta para iniciar un viaje
@app.route("/start_trip", methods=["POST"])
def start_trip():
    data = request.json
    
    # Generar un dominio aleatorio
    dominio_aleatorio = generate_random_domain()  # Llamar a la función para generar un dominio aleatorio
    trip_id = str(uuid.uuid4())
    
    # Crear el mensaje de viaje con el dominio aleatorio
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
            "dominio": dominio_aleatorio,  # Asignar el dominio aleatorio aquí
            "dominioSemi": data["dominioSemi"],
            "precintos": data["precintos"]
        }
    }
    
    # Guardar información del viaje activo
    active_trips[trip_id] = {
        "dominio": dominio_aleatorio,
        "start_time": datetime.now(timezone.utc),
        "telemetry_events": []
    }
    
    # Publicar mensaje de viaje
    success = publish_message(TOPIC_VIAJE, trip_message)
    
    if success:
        # Iniciar un hilo para la simulación de telemetría usando el dominio aleatorio
        threading.Thread(target=simulate_telemetry, args=(trip_id, dominio_aleatorio)).start()
        
        # Responder con el estado, el dominio generado y el id de viaje
        return jsonify({
            "status": "viaje iniciado", 
            "dominio": dominio_aleatorio, 
            "id_viaje": trip_id
        })
    else:
        return jsonify({"status": "error", "message": "Error al publicar mensaje de viaje"}), 500

# Ruta para obtener el estado de un viaje
@app.route("/trip_status/<trip_id>", methods=["GET"])
def trip_status(trip_id):
    if trip_id in active_trips:
        return jsonify({
            "status": "active",
            "trip_info": active_trips[trip_id]
        })
    else:
        return jsonify({"status": "not_found"}), 404

# Ruta para obtener los eventos de telemetría de un viaje
@app.route("/telemetry/<trip_id>", methods=["GET"])
def get_telemetry(trip_id):
    if trip_id in active_trips:
        return jsonify({
            "status": "success",
            "telemetry": active_trips[trip_id]["telemetry_events"]
        })
    else:
        return jsonify({"status": "not_found"}), 404

# Función para simular telemetría más realista
def simulate_telemetry(trip_id, dominio):
    # Definir una ruta más realista (coordenadas para una ruta)
    # Usando aproximadamente las coordenadas de tu ejemplo pero haciendo una ruta más larga
    base_lat = 47.4076
    base_long = -8.5531
    
    # Crear una ruta simulada con 10 puntos, añadiendo variación progresiva
    route = []
    for i in range(10):
        # Incrementar de manera progresiva para simular movimiento
        lat = base_lat + (i * 0.002) + random.uniform(-0.0005, 0.0005)
        long = base_long + (i * 0.003) + random.uniform(-0.0005, 0.0005)
        route.append((lat, long))
    
    for i, (lat, long) in enumerate(route):
        # Código de evento aleatorio (entre 70 y 90 para mantenerlo en un rango específico)
        evento_code = random.randint(70, 90)
        
        # Crear mensaje de telemetría
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
        
        # Guardar el evento de telemetría para este viaje
        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "position": {"lat": lat, "long": long},
                "events": [evento_code]
            })
        
        # Publicar mensaje de telemetría
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"Mensaje de telemetría enviado para dominio {dominio}, posición {lat}, {long}")
        
        # Esperar entre mensajes (tiempo variable para mayor realismo)
        time.sleep(random.uniform(4.0, 6.0))
    
    # Después de completar la ruta, marcar el viaje como completado
    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = datetime.now(timezone.utc).isoformat()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)