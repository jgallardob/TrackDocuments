FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para PyMuPDF (swig, mupdf librerías si son necesarias, pero pip suele traer el wheel)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Directorio para la bóveda (volumen persistente recomendado)
RUN mkdir -p /app/vault

EXPOSE 9090

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9090"]
