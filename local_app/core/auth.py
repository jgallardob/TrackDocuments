import json
import os
from fastapi import Cookie, HTTPException, status
from jose import JWTError
from .security import decode_access_token

USERS_DB_PATH = os.getenv("USERS_DB_PATH", "users_db.json")

def load_users_db() -> list:
    """Carga y retorna la base de datos estática de usuarios desde el JSON."""
    try:
        with open(USERS_DB_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def get_user_by_username(username: str) -> dict:
    """Busca un usuario por su nombre de usuario."""
    users = load_users_db()
    for user in users:
        if user.get("username") == username:
            return user
    return None

def get_current_user_from_cookie(access_token: str = Cookie(None)) -> dict:
    """Extrae el token de la cookie HttpOnly y valida el usuario activo."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales de autenticación inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not access_token:
        raise credentials_exception
    
    try:
        payload = decode_access_token(access_token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = get_user_by_username(username)
    if user is None:
        raise credentials_exception
        
    if user.get("status") != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inhabilitado"
        )
        
    return user
