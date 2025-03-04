# Aplicación de Simulación de Viajes y Telemetría

Esta aplicación es una simulación de viajes y telemetría utilizando Flask y Google Cloud Pub/Sub. Permite iniciar viajes, simular eventos de telemetría y consultar el estado de los viajes activos.

## Requisitos

- Python 3.7+
- Flask
- dotenv
- google-cloud-pubsub

## Instalación

1. Clona el repositorio:

    ```bash
    git clone https://github.com/Gastunchy/simulador_py.git
    cd simulador_py
    git checkout Simulador_local
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
    PROJECT_ID=<ID_DEL_PROYECTO_receptor_pubsub>
    TOPIC_VIAJE=<TOPICO_DE_VIAJES_receptor_pubsub>
    TOPIC_TELEMETRIA=<TOPICO_DE_TELEMETRIA_receptor_pubsub>
    GOOGLE_APPLICATION_CREDENTIALS=<RUTA_A_CREDENCIALES_JSON>
    ```

## Uso

1. Inicia la aplicación Flask:

    ```bash
    python app.py
    ```

2. Abre tu navegador y navega a `http://localhost:8080` para ver la página de inicio.

## Funciones Principales

- `generate_random_domain()`: Genera un dominio aleatorio de 6 caracteres.
- `publish_message(topic_name, message)`: Publica un mensaje en el tema de Pub/Sub especificado.
- `simulate_telemetry(trip_id, dominio)`: Simula eventos de telemetría para un viaje.

## Contribuciones

Las contribuciones son bienvenidas. Por favor, abre un issue o un pull request para discutir cualquier cambio que desees realizar.

## Licencia

Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.