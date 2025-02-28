# Imagen base de Python
FROM python:3.9

# Establecer el directorio de trabajo
WORKDIR /app

# Copiar archivos al contenedor
COPY . .

# Instalar dependencias
RUN pip install flask google-cloud-pubsub

# Exponer el puerto 8080
EXPOSE 8080

# Ejecutar la aplicación
CMD ["python", "simulador.py"]
