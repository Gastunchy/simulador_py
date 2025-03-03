from flask import Flask, render_template, request, jsonify
import json
import uuid
import time
import threading
from google.cloud import pubsub_v1
from datetime import datetime, timezone, timedelta
import random
import string
import math

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
    # Coordenadas de la Ruta Nacional 9 entre Córdoba y Rosario
    # Puntos principales de la ruta (ciudades/localidades importantes)
    waypoints = [
        (-31.4135, -64.1810),  # Córdoba Capital
        (-31.6539, -64.0963),  # Pilar
        (-31.9432, -63.8939),  # Villa María
        (-32.2422, -63.8065),  # Bell Ville
        (-32.4304, -63.2399),  # Marcos Juárez
        (-32.7148, -62.1046),  # Cañada de Gómez
        (-32.9442, -60.6505)   # Rosario
    ]
    
    # Generar una ruta detallada interpolando entre waypoints
    detailed_route = []
    for i in range(len(waypoints) - 1):
        # Obtener waypoint actual y siguiente
        curr_lat, curr_long = waypoints[i]
        next_lat, next_long = waypoints[i + 1]
        
        # Calcular cuántos puntos generar entre estos waypoints
        # Más puntos para segmentos más largos
        distance = ((next_lat - curr_lat)**2 + (next_long - curr_long)**2)**0.5
        # ~25-40 puntos entre ciudades principales, ajustado por distancia real
        num_points = max(5, int(distance * 2000))
        
        # Generar puntos a lo largo de este segmento con variaciones realistas
        for j in range(num_points):
            # Interpolación lineal entre waypoints
            ratio = j / num_points
            lat = curr_lat + (next_lat - curr_lat) * ratio
            long = curr_long + (next_long - curr_long) * ratio
            
            # Añadir "ruido" realista de GPS
            gps_noise_lat = random.uniform(-0.0001, 0.0001)  # ~10-15 metros de precisión
            gps_noise_long = random.uniform(-0.0001, 0.0001)
            
            # Simular desviaciones de la ruta (por obras, desvíos, etc.)
            # Las desviaciones son mayores en el medio del segmento y menores cerca de las ciudades
            deviation_factor = 0.7 * (1 - abs(2 * ratio - 1))
            road_deviation_lat = random.uniform(-0.0003, 0.0003) * deviation_factor
            road_deviation_long = random.uniform(-0.0003, 0.0003) * deviation_factor
            
            # Aplicar ruido y desviación
            lat += gps_noise_lat + road_deviation_lat
            long += gps_noise_long + road_deviation_long
            
            detailed_route.append((lat, long))
    
    # Variables para simular cambios de velocidad
    # Velocidad inicial ~100 km/h (velocidad común en la RN9)
    current_speed = random.uniform(95, 105)
    
    # Manejo de timestamps para timing realista
    current_time = datetime.now(timezone.utc)
    
    # Simular clima y condiciones de tráfico
    weather_conditions = random.choice(["clear", "rain", "cloudy"])
    traffic_density = random.choice(["low", "medium", "high"])
    
    # Ajustar velocidad base según condiciones
    if weather_conditions == "rain":
        current_speed *= 0.85  # Reducir velocidad en lluvia
    if traffic_density == "high":
        current_speed *= 0.8   # Reducir velocidad en tráfico denso
    elif traffic_density == "medium":
        current_speed *= 0.9   # Reducir un poco en tráfico medio
    
    # Iterar a través de la ruta detallada
    for i, (lat, long) in enumerate(detailed_route):
        # Simular cambios de velocidad - más lento cerca de ciudades, más rápido en tramos abiertos
        if i > 0 and i < len(detailed_route) - 1:
            # Verificar si estamos cerca de un waypoint (ciudad)
            near_city = False
            city_name = ""
            for idx, (city_lat, city_long) in enumerate(waypoints):
                distance_to_city = ((lat - city_lat)**2 + (long - city_long)**2)**0.5
                if distance_to_city < 0.03:  # Si estamos a ~3km de una ciudad
                    near_city = True
                    # Asociar índice del waypoint con nombre de ciudad
                    city_names = ["Córdoba", "Pilar", "Villa María", "Bell Ville", "Marcos Juárez", "Cañada de Gómez", "Rosario"]
                    city_name = city_names[idx]
                    break
            
            # Ajustar velocidad según cercanía a ciudades y calcular eventos
            if near_city:
                # Reducir velocidad significativamente cerca de ciudades
                target_speed = random.uniform(50, 70)
                # Reducción gradual de velocidad
                current_speed = current_speed * 0.9 + target_speed * 0.1
                # Evento de entrada a zona urbana
                evento_code = random.randint(81, 85)
                # Añadir información de la ciudad
                city_info = f"Cerca de {city_name}"
            else:
                # Calcular cambios de dirección para detectar curvas
                prev_lat, prev_long = detailed_route[i-1]
                next_lat, next_long = detailed_route[i+1] if i < len(detailed_route) - 2 else detailed_route[i]
                
                direction_change = abs((next_lat - lat) * (lat - prev_lat) + 
                                      (next_long - long) * (long - prev_long))
                
                # Ajustar velocidad basado en curvas
                if direction_change < 0.00001:  # Curva pronunciada
                    current_speed = max(70, current_speed * 0.92)
                    evento_code = 83  # Código específico para curva
                    city_info = "Curva pronunciada"
                elif direction_change < 0.0001:  # Curva moderada
                    current_speed = max(80, current_speed * 0.95)
                    evento_code = 82  # Código para curva moderada
                    city_info = "Curva moderada"
                else:  # Tramo recto
                    # Velocidad máxima típica en RN9: ~110-120 km/h
                    current_speed = min(115, current_speed * 1.02)
                    
                    # Eventos en tramo recto basados en velocidad
                    if current_speed > 105:
                        evento_code = 78  # Alta velocidad en ruta
                        city_info = "Tramo recto - velocidad crucero"
                    else:
                        evento_code = 70  # Velocidad normal
                        city_info = "Tramo recto"
        else:
            # Inicio o fin del viaje
            if i == 0:
                evento_code = 90  # Salida de Córdoba
                current_speed = 50  # Velocidad inicial baja
                city_info = "Saliendo de Córdoba"
            else:
                evento_code = 91  # Llegada a Rosario
                current_speed = 40  # Reducción final de velocidad
                city_info = "Llegando a Rosario"
        
        # Calcular tiempo basado en distancia y velocidad
        if i > 0:
            prev_lat, prev_long = detailed_route[i-1]
            # Distancia en km (usando aproximación para conversión de coordenadas)
            # Factor 111 km por grado es una aproximación para esta latitud
            lat_distance = abs(lat - prev_lat) * 111
            long_distance = abs(long - prev_long) * 111 * math.cos(math.radians(lat))
            distance_km = math.sqrt(lat_distance**2 + long_distance**2)
            
            # Tiempo en horas = distancia / velocidad
            time_hours = distance_km / current_speed
            # Convertir a segundos
            time_seconds = time_hours * 3600
            # Añadir algo de aleatoriedad al tiempo
            time_seconds *= random.uniform(0.95, 1.05)
            # Actualizar tiempo actual
            current_time = current_time + timedelta(seconds=time_seconds)
        
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
            "speed": round(current_speed, 1),
            "eventos": [evento_code]
        }
        
        # Guardar el evento de telemetría para este viaje
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
        
        # Publicar mensaje de telemetría
        publish_message(TOPIC_TELEMETRIA, telemetry_message)
        print(f"Mensaje de telemetría enviado: {dominio}, posición ({lat}, {long}), velocidad {round(current_speed, 1)} km/h, {city_info}")
        
        # Esperar un tiempo corto entre mensajes para propósitos de simulación
        time.sleep(random.uniform(0.3, 0.7))
    
    # Después de completar la ruta, marcar el viaje como completado
    if trip_id in active_trips:
        active_trips[trip_id]["status"] = "completed"
        active_trips[trip_id]["end_time"] = current_time.isoformat()
        active_trips[trip_id]["route_summary"] = {
            "origin": "Córdoba",
            "destination": "Rosario",
            "distance_km": 400,  # Aproximadamente 400km entre Córdoba y Rosario
            "duration": (current_time - active_trips[trip_id]["start_time"]).total_seconds() / 3600,  # Duración en horas
            "avg_speed": round(400 / ((current_time - active_trips[trip_id]["start_time"]).total_seconds() / 3600), 1)  # Velocidad promedio
        }

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)