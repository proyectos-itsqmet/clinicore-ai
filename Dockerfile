# Usa una imagen oficial y ligera de Python
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copia primero el archivo de dependencias para aprovechar el caché de Docker
COPY requirements.txt .

# Instala las dependencias sin guardar caché temporal para mantener la imagen ligera
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código del proyecto al contenedor
COPY . .

# Expone el puerto configurado (el predeterminado en app.py es 8000)
EXPOSE 8000

# Comando para iniciar la aplicación Flask
CMD ["python", "app.py"]
