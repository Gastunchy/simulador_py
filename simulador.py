import os
import json
import uuid
import time
import threading
import random
import string
import math
import logging
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template, request, jsonify
from google.cloud import pubsub_v1
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de Pub/Sub
PROJECT_ID = os.getenv("PROJECT_ID")
TOPIC_VIAJE = os.getenv("TOPIC_VIAJE")
TOPIC_TELEMETRIA = os.getenv("TOPIC_TELEMETRIA")
publisher = pubsub_v1.PublisherClient()

# Configurar credenciales de Google Cloud (descomentar si es necesario)
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Almacenamiento en memoria para viajes activos
active_trips = {}

# Configuración de logging
logging.basicConfig(level=logging.INFO)

# Inicializar la aplicación Flask
app = Flask(__name__)

def generate_random_domain(length=6):
    """Genera un dominio aleatorio de longitud especificada."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def publish_message(topic_name, message):
    """Publica un mensaje en un tópico de Pub/Sub."""
    try:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        logging.info(f"Enviando mensaje a {topic_name}")
        future = publisher.publish(topic_path, json.dumps(message).encode("utf-8"))
        future.result()  # Esperar a que se publique
        logging.info(f"Mensaje publicado en {topic_name}")
        return True
    except Exception as e:
        logging.error(f"Error al publicar mensaje en {topic_name}: {str(e)}")
        return False

@app.route("/")
def index():
    """Ruta principal."""
    return render_template("index.html")

@app.route("/favicon.ico")
def favicon():
    """Ruta para el favicon (para evitar error 404)."""
    return '', 204  # Responde con un estado 204 (No Content) para evitar el error 404

@app.route("/start_trip", methods=["POST"])
def start_trip():
    """Inicia un viaje y publica un mensaje en Pub/Sub."""
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
        "start_time": datetime.now(timezone.utc),
        "telemetry_events": []
    }
    
    success = publish_message(TOPIC_VIAJE, trip_message)
    
    if success:
        threading.Thread(target=simulate_telemetry, args=(trip_id, dominio_aleatorio)).start()
        return jsonify({
            "status": "viaje iniciado", 
            "dominio": dominio_aleatorio, 
            "id_viaje": trip_id
        })
    else:
        return jsonify({"status": "error", "message": "Error al publicar mensaje de viaje"}), 500

@app.route("/trip_status/<trip_id>", methods=["GET"])
def trip_status(trip_id):
    """Obtiene el estado de un viaje."""
    if trip_id in active_trips:
        return jsonify({
            "status": "active",
            "trip_info": active_trips[trip_id]
        })
    else:
        return jsonify({"status": "not_found"}), 404

@app.route("/telemetry/<trip_id>", methods=["GET"])
def get_telemetry(trip_id):
    """Obtiene los eventos de telemetría de un viaje."""
    if trip_id in active_trips:
        return jsonify({
            "status": "success",
            "telemetry": active_trips[trip_id]["telemetry_events"]
        })
    else:
        return jsonify({"status": "not_found"}), 404

def simulate_telemetry(trip_id, dominio):
    """Simula telemetría para un viaje."""
    waypoints = [
        (-31.4135, -64.1810),  # Córdoba Capital
        (-31.6539, -64.0963),  # Pilar
        (-31.9432, -63.8939),  # Villa María
        (-32.2422, -63.8065),  # Bell Ville
        (-32.4304, -63.2399),  # Marcos Juárez
        (-32.7148, -62.1046),  # Cañada de Gómez
        (-32.9442, -60.6505)   # Rosario
    ]
    
    detailed_route = generate_detailed_route(waypoints)
    current_speed = random.uniform(95, 105)
    current_time = datetime.now(timezone.utc)
    
    weather_conditions = random.choice(["clear", "rain", "cloudy"])
    traffic_density = random.choice(["low", "medium", "high"])
    
    if weather_conditions == "rain":
        current_speed *= 0.85
    if traffic_density == "high":
        current_speed *= 0.8
    elif traffic_density == "medium":
        current_speed *= 0.9
    
    for i, (lat, long) in enumerate(detailed_route):
        current_speed, evento_code, city_info = adjust_speed_and_event(i, lat, long, detailed_route, waypoints, current_speed)
        
        if i > 0:
            prev_lat, prev_long = detailed_route[i-1]
            lat_distance = abs(lat - prev_lat) * 111
            long_distance = abs(long - prev_long) * 111 * math.cos(math.radians(lat))
            distance_km = math.sqrt(lat_distance**2 + long_distance**2)
            
            time_hours = distance_km / current_speed
            time_seconds = time_hours * 3600
            time_seconds *= random.uniform(0.95, 1.05)
            current_time = current_time + timedelta(seconds=time_seconds)
        
        telemetry_message = {
            "uuid": str(uuid.uuid4()),
            "msgDateTime": current_time.isoformat(),
            "messageType": "evento",
            "deviceID": dominio,
            "deviceVendor": "Integra",
            "deviceType": "emulated",
            "gps": {
                "lat": str(lat),
                "long": str(long)
            },
            "speed": round(current_speed, 1),
            "eventos": [evento_code]
        }
        
        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": current_time.isoformat(),
                "position": {"lat": lat, "long": long},
                "speed": round(current_speed, 1),
                "events": [evento_code],
                "location": city_info,
                "weather": weather_conditions,
                "traffic": traffic_density
            })
        
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        logging.info(f"Mensaje de telemetría enviado: {dominio}, posición ({lat}, {long}), velocidad {round(current_speed, 1)} km/h, {city_info}")
        
        time.sleep(random.uniform(0.3, 0.7))
    
    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = current_time.isoformat()
        active_trips[trip_id]["route_summary"] = {
            "origin": "Córdoba",
            "destination": "Rosario",
            "distance_km": 400,
            "duration": (current_time - active_trips[trip_id]["start_time"]).total_seconds() / 3600,
            "avg_speed": round(400 / ((current_time - active_trips[trip_id]["start_time"]).total_seconds() / 3600), 1)
        }

def generate_detailed_route(waypoints):
    """Genera una ruta detallada interpolando entre waypoints."""
    detailed_route = []
    for i in range(len(waypoints) - 1):
        curr_lat, curr_long = waypoints[i]
        next_lat, next_long = waypoints[i + 1]
        
        distance = ((next_lat - curr_lat)**2 + (next_long - curr_long)**2)**0.5
        num_points = max(5, int(distance * 2000))
        
        for j in range(num_points):
            ratio = j / num_points
            lat = curr_lat + (next_lat - curr_lat) * ratio
            long = curr_long + (next_long - curr_long) * ratio
            
            gps_noise_lat = random.uniform(-0.0001, 0.0001)
            gps_noise_long = random.uniform(-0.0001, 0.0001)
            
            deviation_factor = 0.7 * (1 - abs(2 * ratio - 1))
            road_deviation_lat = random.uniform(-0.0003, 0.0003) * deviation_factor
            road_deviation_long = random.uniform(-0.0003, 0.0003) * deviation_factor
            
            lat += gps_noise_lat + road_deviation_lat
            long += gps_noise_long + road_deviation_long
            
            detailed_route.append((lat, long))
            logging.info(f"Generated coordinate: ({lat}, {long})")
    return detailed_route

def adjust_speed_and_event(i, lat, long, detailed_route, waypoints, current_speed):
    """Ajusta la velocidad y determina el evento basado en la posición."""
    if i > 0 and i < len(detailed_route) - 1:
        near_city = False
        city_name = ""
        for idx, (city_lat, city_long) in enumerate(waypoints):
            distance_to_city = ((lat - city_lat)**2 + (long - city_long)**2)**0.5
            if distance_to_city < 0.03:
                near_city = True
                city_names = ["Córdoba", "Pilar", "Villa María", "Bell Ville", "Marcos Juárez", "Cañada de Gómez", "Rosario"]
                city_name = city_names[idx]
                break
        
        if near_city:
            target_speed = random.uniform(50, 70)
            current_speed = current_speed * 0.9 + target_speed * 0.1
            evento_code = random.randint(81, 85)
            city_info = f"Cerca de {city_name}"
        else:
            prev_lat, prev_long = detailed_route[i-1]
            next_lat, next_long = detailed_route[i+1] if i < len(detailed_route) - 2 else detailed_route[i]
            
            direction_change = abs((next_lat - lat) * (lat - prev_lat) + 
                                  (next_long - long) * (long - prev_long))
            
            if direction_change < 0.00001:
                current_speed = max(70, current_speed * 0.92)
                evento_code = 83
                city_info = "Curva pronunciada"
            elif direction_change < 0.0001:
                current_speed = max(80, current_speed * 0.95)
                evento_code = 82
                city_info = "Curva moderada"
            else:
                current_speed = min(115, current_speed * 1.02)
                
                if current_speed > 105:
                    evento_code = 78
                    city_info = "Tramo recto - velocidad crucero"
                else:
                    evento_code = 70
                    city_info = "Tramo recto"
    else:
        if i == 0:
            evento_code = 90
            current_speed = 50
            city_info = "Saliendo de Córdoba"
        else:
            evento_code = 91
            current_speed = 40
            city_info = "Llegando a Rosario"
    
    return current_speed, evento_code, city_info

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)