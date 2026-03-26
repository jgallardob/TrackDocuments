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

app = FastAPI(title="TrackDocuments API - Core Foundation")

VAULT_DIR = Path(os.getenv("VAULT_DIR", "vault"))
VAULT_DIR.mkdir(parents=True, exist_ok=True)

# Helper Metadata (PR#1: Basic)
def get_metadata():
    meta_path = VAULT_DIR / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    return {}

def save_metadata(data):
    (VAULT_DIR / "metadata.json").write_text(json.dumps(data, indent=2))

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
    """Listado simplificado de archivos para PR#1."""
    meta = get_metadata()
    files_list = []
    for k, v in meta.items():
        if isinstance(v, dict):
            files_list.append({"id": k, "name": v["original_name"], "is_valid": v.get("is_valid", True)})
        else:
            files_list.append({"id": k, "name": v})
    return {"files": files_list}
