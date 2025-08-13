import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.services.cookie_manager import CookieManager
from app.services.youtube_cookie_updater import login_youtube_and_save_cookies

router = APIRouter()
API_TOKEN = os.getenv("CRON_SECRET_TOKEN")

def update_youtube_cookies_task():
    """Ejecuta el login y guarda las cookies"""
    email = os.getenv("YOUTUBE_EMAIL")
    password = os.getenv("YOUTUBE_PASSWORD")

    if not email or not password:
        print("❌ No se puede actualizar cookies: faltan credenciales en .env")
        return

    print(f"🔄 Actualizando cookies para {email}")
    login_youtube_and_save_cookies()
    print("✅ Cookies actualizadas correctamente")

@router.post("/cookies/update")
async def update_cookies(request: Request, background_tasks: BackgroundTasks):
    """Inicia la actualización de cookies en segundo plano"""
    token = request.headers.get("Authorization")
    if token != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=403, detail="Unauthorized")

    background_tasks.add_task(update_youtube_cookies_task)
    return {"status": "started", "message": "Actualización de cookies en proceso"}
