# Aplicación de Simulación de Viajes y Telemetría

Esta aplicación es una simulación de viajes y telemetría utilizando Flask y Google Cloud Pub/Sub. Permite iniciar viajes, simular eventos de telemetría y consultar el estado de los viajes activos.

## Requisitos

- Python 3.7+
- Google Cloud SDK
- Flask
- dotenv
- google-cloud-pubsub

## Instalación

1. Clona el repositorio:

    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd <NOMBRE_DEL_REPOSITORIO>
    ```

2. Crea y activa un entorno virtual:

    ```bash
    python -m venv venv
    source venv/bin/activate  # En Windows usa `venv\Scripts\activate`
    ```

3. Instala las dependencias:

    ```bash
    pip install -r requirements.txt
    ```

4. Crea un archivo `.env` en la raíz del proyecto con las siguientes variables:

    ```env
    PROJECT_ID=<ID_DEL_PROYECTO>
    TOPIC_VIAJE=<TOPICO_DE_VIAJES>
    TOPIC_TELEMETRIA=<TOPICO_DE_TELEMETRIA>
    GOOGLE_APPLICATION_CREDENTIALS=<RUTA_A_CREDENCIALES_JSON>
    PORT=8080
    FLASK_ENV=development
    ```

## Uso

1. Inicia la aplicación Flask:

    ```bash
    python app.py
    ```

2. Abre tu navegador y navega a `http://localhost:8080` para ver la página de inicio.

## Endpoints

### `GET /`

Renderiza la página de inicio.

### `POST /start_trip`

Inicia un nuevo viaje y comienza a simular telemetría.

- **Request Body**:
    ```json
    {
        "tipoViaje": "tipo_de_viaje",
        "idSucursalOrigen": "id_origen",
        "idSucursalDestino": "id_destino",
        "hr": "hora",
        "transportista": "nombre_transportista",
        "dominioSemi": "dominio_semi",
        "precintos": "precintos"
    }
    ```

- **Response**:
    ```json
    {
        "status": "viaje iniciado",
        "dominio": "dominio_aleatorio",
        "id_viaje": "id_del_viaje"
    }
    ```

### `GET /trip_status/<trip_id>`

Consulta el estado de un viaje activo.

- **Response**:
    ```json
    {
        "status": "active",
        "trip_info": {
            "dominio": "dominio_aleatorio",
            "start_time": "hora_de_inicio",
            "telemetry_events": [],
            "status": "active"
        }
    }
    ```

### `GET /telemetry/<trip_id>`

Obtiene los eventos de telemetría de un viaje activo.

- **Response**:
    ```json
    {
        "status": "success",
        "telemetry": [
            {
                "timestamp": "hora_del_evento",
                "position": {
                    "lat": "latitud",
                    "long": "longitud"
                },
                "events": [evento]
            }
        ]
    }
    ```

## Funciones Principales

- `generate_random_domain()`: Genera un dominio aleatorio de 6 caracteres.
- `publish_message(topic_name, message)`: Publica un mensaje en el tema de Pub/Sub especificado.
- `simulate_telemetry(trip_id, dominio)`: Simula eventos de telemetría para un viaje.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o un pull request para discutir cualquier cambio que desees realizar.

## Licencia

Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.