import os
import io
import base64
import json
import boto3
from email.message import Message

# Se asume que el modulo 'core' estara empaquetado junto al handler o en el layer
from core.watermark import apply_forensic_watermark

S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "dlp-vault-cloud")
s3_client = boto3.client("s3")

def lambda_handler(event, context):
    """
    Punto de entrada Lambda proxy (API Gateway). Encamina subidas y descargas.
    """
    path = event.get("resource", "") or event.get("path", "")
    http_method = event.get("httpMethod", "")
    
    # Resolucion de ID de usuario del autorizador API Gateway (Cognito)
    request_context = event.get("requestContext", {})
    authorizer = request_context.get("authorizer", {})
    claims = authorizer.get("claims", {})
    
    # Mocking predeterminado para pruebas si authorizer no engancha a lambda proxy test
    user_id = claims.get("sub", "aws-cognito-fallback-id")

    if path.endswith("/upload") and http_method == "POST":
        return handle_upload(event, user_id)
        
    elif path.startswith("/share/") and http_method == "GET":
        doc_id = event["pathParameters"]["doc_id"]
        return handle_share(doc_id, user_id)
        
    else:
        return {
            "statusCode": 404,
            "body": json.dumps({"error": "Ruta no encontrada AWS DLP proxy."})
        }

def handle_upload(event, user_id):
    """Extrae el PDF binario de un form multipart o payload raw y sube a S3."""
    try:
        if event.get("isBase64Encoded"):
            body = base64.b64decode(event["body"])
        else:
            body = event["body"].encode("utf-8")
            
        # Extracción y ofuscación absoluta de metadatos (UUID)
        import uuid
        doc_id = f"{uuid.uuid4().hex}.pdf"
        
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"vault/{doc_id}",
            Body=body,
            ContentType="application/pdf"
        )
        print(f"[AUDIT] Subida a S3 exitosa por {user_id}. DOC_ID: {doc_id}")
        
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Archivo seguro en S3 bóveda forense.", "doc_id": doc_id})
        }

    except Exception as e:
        print(f"Error procesando upload S3: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Falla de ingesta"})}

def handle_share(doc_id, user_id):
    """
    Descarga archivo original de S3, invoca el módulo forense PyMuPDF en memoria y 
    transmite base64 a API Gateway para ser enviado como `application/pdf`.
    """
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=f"vault/{doc_id}")
        pdf_bytes = response['Body'].read()
        
        # En memoria / io.BytesIO procesamos usando PyMuPDF
        secured_pdf_bytes = apply_forensic_watermark(pdf_bytes, user_id)
        
        print(f"[AUDIT-FORENSIC-CLOUD] Descarga CloudWatch. Intercepción DLP ejecutada. USER_ID={user_id} DOC={doc_id}")
        
        # API Gateway soporta base64 payload response para output en binario
        b64_output = base64.b64encode(secured_pdf_bytes).decode("utf-8")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/pdf",
                "Content-Disposition": f"attachment; filename=secured_{doc_id}"
            },
            "isBase64Encoded": True,
            "body": b64_output
        }

    except s3_client.exceptions.NoSuchKey:
        return {"statusCode": 404, "body": json.dumps({"error": "Documento no hallado en S3"})}
    except Exception as e:
        print(f"Error procesando forense S3: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Error interno del motor DLP"})}
