# TrackDocuments - DLP y Trazabilidad Forense de PDFs

Implementación "Privacy by Design" para el control descentralizado de fugas de datos y trazabilidad imperceptible sobre formato nativo de PDFs (`io.BytesIO`) de manera dual: **Serverless Nube (AWS)** y **Contenedor Local (Docker/FastAPI)**.

## Características Principales

- **Esteganografía Forense (Yellow Dots)**: Inyección de micro-marcas amarillas (RGB 1,1,0) con opacidad del 3%. Invisibles al ojo humano pero detectables mediante ajustes de contraste.
- **Árbol de Auditoría en Tiempo Real**: Seguimiento jerárquico de quién, cuándo y qué documento ha sido extraído de la bóveda.
- **Invalidación No-Destructiva (Soft-Invalidation)**: Los archivos revocados permanecen físicamente en la bóveda para auditoría forense, pero su acceso es bloqueado lógicamente con un aviso de "Documento No Válido".
- **Aislamiento de Frontera (XSS Mitigation)**: Lógica de frontend desacoplada en `app.js` bajo políticas estrictas de Content Security Policy (CSP).
- **Iconografía SVG y Política Emoji-Free**: Interfaz 100% libre de emojis mediante el uso de vectores SVG premium, garantizando máxima compatibilidad en backoffice y logs.
- **Ofuscación de Bóveda**: Los archivos se almacenan como blobs con nombres UUID aleatorios, eliminando metadatos físicos del sistema de archivos.

---

## Requerimientos Arquitecturales

1. **Procesamiento Cero Disco (Memory IO)**: PyMuPDF procesa todo el flujo en memoria ram, evitando el uso de `/tmp`.
2. **Marca Forense Latente**: Patrón repetitivo global que incluye el ID del responsable y marca de tiempo en cada página.
3. **Monolito Desacoplado**: Motor de watermarking (`core/watermark.py`) compartido entre el entorno Docker y AWS Lambda.

---

## Despliegue Local (Docker Compose)

Esta fase emula el servidor API completo acoplado con Proxy Inverso NGINX.

1. **Construcción e Inicialización**:
    ```bash
    docker compose up --build -d
    ```
2. **Acceso a la Interfaz**: `http://localhost:8000/`
    * Usuarios (password global `admin123`): `admin`, `user1`, `user2_disabled`
3. **Logs de Auditoría**:
    ```bash
    docker logs -f dlp_fastapi
    ```

---

## Infraestructura en la Nube (AWS Terraform)

El stack AWS implementa el backend mediante Lambda + API Gateway + Cognito.

1. **Despliegue de Infraestructura**:
    ```bash
    cd aws_infra
    terraform init
    terraform apply -auto-approve
    ```
2. **Sincronización de Identidades**:
    ```bash
    cd ../scripts
    python cognito_sync.py --pool-id [TU_POOL_ID]
    ```

---

## Compilación de Capas (Lambda Layer PyMuPDF)

`PyMuPDF` requiere dependencias binarias de C++. Para AWS Lambda, se debe compilar en un entorno Amazon Linux:

```bash
docker run -v "$PWD":/var/task -it amazon/aws-sam-cli-build-image-python3.11 bash

mkdir -p /var/task/layer/python
pip install --platform manylinux2014_x86_64 --target /var/task/layer/python --implementation cp --python-version 3.11 --only-binary=:all: --upgrade PyMuPDF
cd /var/task/layer
zip -r /var/task/aws_infra/pymupdf_layer_amazonlinux.zip python/
exit
```
Finalizada la compilación, `terraform apply` distribuirá el binario optimizado.
