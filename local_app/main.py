import os
import io
import shutil
import uuid
import json
from pathlib import Path
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Response
from fastapi.security import OAuth2PasswordRequestForm

from core.security import verify_password, create_access_token
from core.auth import load_users_db, get_current_user_from_cookie

from core.watermark import apply_forensic_watermark

app = FastAPI(title="TrackDocuments - DLP Forensic Vault")

# ... (get_metadata and save_metadata stay the same)

@app.get("/share/{doc_id}")
async def share_document_landing(doc_id: str):
    """Página de aterrizaje para descarga segura. Verifica validez del documento."""
    meta = get_metadata()
    doc = meta.get(doc_id)
    
    if not doc:
        return Response(content="<html><body><h1>404 - Documento no encontrado</h1></body></html>", media_type="text/html")
    
    if not doc.get("is_valid", True):
        return Response(content="""
            <html><body style="background:#0d1117; color:#f85149; font-family:sans-serif; text-align:center; padding-top:100px;">
                <svg viewBox="0 0 24 24" width="80" height="80" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>
                <h1>Acceso Revocado</h1>
                <p>Este documento ha sido invalidado por el autor o el administrador del sistema.</p>
            </body></html>
        """, media_type="text/html")

    return Response(content=f"""
        <html><body style="background:#0d1117; color:#e2e8f0; font-family:sans-serif; text-align:center; padding-top:100px;">
            <h1>TrackDocuments - Descarga Segura</h1>
            <p>Archivo: <b>{doc['original_name']}</b></p>
            <form action="/api/download/{doc_id}" method="GET">
                <button type="submit" style="background:#3b82f6; color:white; border:none; padding:12px 24px; border-radius:6px; cursor:pointer;">Autorizar y Descargar</button>
            </form>
        </body></html>
    """, media_type="text/html")

@app.get("/api/download/{doc_id}")
async def download_document(doc_id: str, current_user: dict = Depends(get_current_user_from_cookie)):
    """Descarga con inyección dinámica de marca de agua forense."""
    meta = get_metadata()
    doc = meta.get(doc_id)
    
    if not doc or not doc.get("is_valid", True):
        raise HTTPException(status_code=403, detail="Documento inválido o no encontrado")
    
    file_path = VAULT_DIR / f"{doc_id}.blob"
    with open(file_path, "rb") as f:
        content = f.read()
    
    # Aplicar marca forense
    watermarked_pdf = apply_forensic_watermark(content, current_user["user_id"])
    
    # Registrar descarga para auditoría
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    doc["downloads"].append(f"{current_user['user_id']} @ {timestamp}")
    save_metadata(meta)
    
    return Response(
        content=watermarked_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=PROT_{doc['original_name']}"}
    )

@app.delete("/files/{doc_id}")
async def invalidate_document(doc_id: str, current_user: dict = Depends(get_current_user_from_cookie)):
    """Soft-Invalidation: Invalida el acceso sin borrar el binario físico."""
    meta = get_metadata()
    if doc_id not in meta:
        raise HTTPException(status_code=404, detail="No encontrado")
    
    meta[doc_id]["is_valid"] = False
    save_metadata(meta)
    return {"message": "Documento invalidado para acceso externo"}

@app.post("/login")
async def login_for_access_token(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    """Autentica al usuario y emite un JWT en Cookie HttpOnly."""
    users = load_users_db()
    user = next((u for u in users if u["username"] == form_data.username), None)
    
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
        
    access_token = create_access_token(subject=user["username"])
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=3600,
        samesite="lax",
        secure=False 
    )
    
    print(f"[AUDIT] Inicio de sesión exitoso: {user['user_id']}")
    return {"message": "Autenticación exitosa", "user_id": user["user_id"]}

@app.get("/me")
async def get_my_session(current_user: dict = Depends(get_current_user_from_cookie)):
    """Valida la sesión activa."""
    return {"user_id": current_user["user_id"]}

@app.post("/logout")
async def logout(response: Response):
    """Limpia la cookie de sesión."""
    response.delete_cookie("access_token")
    return {"message": "Sesión terminada"}

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...), 
    current_user: dict = Depends(get_current_user_from_cookie)
):
    """Ingesta segura de PDF con ofuscación UUID y registro de auditoría."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="El archivo no es un PDF")
        
    share_id = f"shr_{uuid.uuid4().hex[:12]}"
    file_path = VAULT_DIR / f"{share_id}.blob"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Metadata Base (Forense v1)
    meta = get_metadata()
    meta[share_id] = {
        "original_name": file.filename,
        "uploaded_by": current_user["user_id"],
        "is_valid": True,
        "downloads": []
    }
    save_metadata(meta)
        
    print(f"[AUDIT] Documento '{file.filename}' asegurado por {current_user['user_id']}")
    return {"message": "Documento asegurado estructuralmente", "filename": share_id}

@app.get("/files")
async def list_documents(current_user: dict = Depends(get_current_user_from_cookie)):
    """Retorna listado maestro y el sub-árbol de auditoría local para el autor actual."""
    try:
        meta = get_metadata()
        files_list = []
        audit_tree = []
        
        for k, v in meta.items():
            if isinstance(v, dict):
                files_list.append({
                    "id": k, 
                    "name": v["original_name"],
                    "is_valid": v.get("is_valid", True)
                })
                # Filtramos el arbol solo a lo que el usuario subió (Ownership)
                if v.get("uploaded_by") == current_user["user_id"]:
                    audit_tree.append({
                        "id": k, 
                        "name": v["original_name"], 
                        "is_valid": v.get("is_valid", True),
                        "downloads": v.get("downloads", [])
                    })
            else:
                files_list.append({"id": k, "name": v})
                
        return {"files": files_list, "audit_tree": audit_tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error leyendo el registro del vault")
