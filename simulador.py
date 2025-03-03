from flask import Flask, render_template, request, jsonify
import json
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone
import random
import string

app = Flask(__name__)

# Configuración de Pub/Sub
PROJECT_ID = "crypto-avatar-452213-k0"
TOPIC_VIAJE = "viaje-topic"
TOPIC_TELEMETRIA = "telemetria-topic"
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
    # Define starting and ending points
    # Using real-world coordinates for a sensible route
    start_lat, start_long = 47.4076, -8.5531
    end_lat, end_long = 47.4376, -8.5231  # Destination ~3-4km away
    
    # Create waypoints to simulate a realistic route (like following roads)
    # These act as major turns or intersections a vehicle would follow
    waypoints = [
        (start_lat, start_long),  # Starting point
        (start_lat + 0.008, start_long + 0.003),  # First turn
        (start_lat + 0.012, start_long + 0.009),  # Second turn
        (start_lat + 0.018, start_long + 0.014),  # Third turn
        (start_lat + 0.025, start_long + 0.022),  # Fourth turn
        (end_lat, end_long)  # Destination
    ]
    
    # Generate detailed route by interpolating between waypoints
    detailed_route = []
    for i in range(len(waypoints) - 1):
        # Get current and next waypoint
        curr_lat, curr_long = waypoints[i]
        next_lat, next_long = waypoints[i + 1]
        
        # Calculate how many points to generate between these waypoints
        # More points for longer segments
        distance = ((next_lat - curr_lat)**2 + (next_long - curr_long)**2)**0.5
        num_points = max(3, int(distance * 1000))  # Minimum 3 points, scaled by distance
        
        # Generate points along this segment with realistic variations
        for j in range(num_points):
            # Linear interpolation between waypoints
            ratio = j / num_points
            lat = curr_lat + (next_lat - curr_lat) * ratio
            long = curr_long + (next_long - curr_long) * ratio
            
            # Add realistic GPS noise/drift
            gps_noise = random.uniform(-0.00008, 0.00008)  # ~5-10 meter accuracy
            
            # Add road-following behavior (vehicles tend to stay on roads)
            # Deviation is higher at the start of segments and reduces as approaching waypoints
            deviation_factor = 0.5 * (1 - abs(2 * ratio - 1))  # Peaks in the middle of segments
            road_deviation = random.uniform(-0.0001, 0.0001) * deviation_factor
            
            # Apply noise and deviation
            lat += gps_noise + road_deviation
            long += gps_noise + road_deviation
            
            detailed_route.append((lat, long))
    
    # Variables to simulate speed changes
    current_speed = random.uniform(50, 70)  # Starting speed in km/h
    
    # Timestamp handling for realistic timing
    current_time = datetime.now(timezone.utc)
    
    for i, (lat, long) in enumerate(detailed_route):
        # Simulate speed changes - slow down near turns, speed up on straightaways
        if i > 0 and i < len(detailed_route) - 1:
            prev_lat, prev_long = detailed_route[i-1]
            next_lat, next_long = detailed_route[i+1]
            
            # Calculate directional change to detect turns
            direction_change = abs((next_lat - lat) * (lat - prev_lat) + 
                                  (next_long - long) * (long - prev_long))
            
            # Adjust speed based on turns (lower number = sharper turn)
            if direction_change < 0.00001:  # Sharp turn
                current_speed = max(20, current_speed * 0.85)  # Slow down significantly
            elif direction_change < 0.0001:  # Moderate turn
                current_speed = max(30, current_speed * 0.9)  # Slow down moderately
            else:  # Straight section
                current_speed = min(90, current_speed * 1.05)  # Speed up gradually
        
        # Calculate time based on distance and speed
        if i > 0:
            prev_lat, prev_long = detailed_route[i-1]
            # Distance in km (approximate using Haversine would be better)
            distance_km = ((lat - prev_lat)**2 + (long - prev_long)**2)**0.5 * 111
            # Time in hours = distance / speed
            time_hours = distance_km / current_speed
            # Convert to seconds
            time_seconds = time_hours * 3600
            # Add some randomness to time
            time_seconds *= random.uniform(0.9, 1.1)
            # Update current time
            current_time = current_time + datetime.timedelta(seconds=time_seconds)
        
        # Código de evento contextual
        # Generate more meaningful event codes
        # 70-75: Regular movement events
        # 76-80: Speed-related events
        # 81-85: Turn-related events
        # 86-90: Special conditions
        
        if current_speed > 80:
            evento_code = random.randint(76, 80)  # Speed-related
        elif i > 0 and i < len(detailed_route) - 1:
            prev_lat, prev_long = detailed_route[i-1]
            next_lat, next_long = detailed_route[i+1]
            direction_change = abs((next_lat - lat) * (lat - prev_lat) + 
                                  (next_long - long) * (long - prev_long))
            
            if direction_change < 0.0001:  # Turn detected
                evento_code = random.randint(81, 85)  # Turn-related
            else:
                evento_code = random.randint(70, 75)  # Regular movement
        else:
            # Start or end of journey
            evento_code = random.randint(86, 90)  # Special condition
        
        # Crear mensaje de telemetría
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
            "eventos": [evento_code]
        }
        
        # Añadir velocidad a los datos si está disponible
        if current_speed:
            telemetry_message["speed"] = round(current_speed, 1)
        
        # Guardar el evento de telemetría para este viaje
        if trip_id in active_trips:
            active_trips[trip_id]["telemetry_events"].append({
                "timestamp": current_time.isoformat(),
                "position": {"lat": lat, "long": long},
                "speed": round(current_speed, 1),
                "events": [evento_code]
            })
        
        # Publicar mensaje de telemetría
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"Mensaje de telemetría enviado para dominio {dominio}, posición {lat}, {long}, velocidad {round(current_speed, 1)} km/h")
        
        # Wait a short time between message publishing for simulation purposes
        # This doesn't affect the simulated timestamps
        time.sleep(random.uniform(0.5, 1.5))
    
    # Después de completar la ruta, marcar el viaje como completado
    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = datetime.now(timezone.utc).isoformat()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)