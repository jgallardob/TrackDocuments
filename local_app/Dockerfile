FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para PyMuPDF (swig, mupdf librerías si son necesarias, pero pip suele traer el wheel)
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Asegurar directorio de bóveda (punto de montaje de volumen)
RUN mkdir -p /app/vault

COPY . .

WORKDIR /app/local_app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
