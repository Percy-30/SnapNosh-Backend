import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.services.youtube_cookie_updater import login_youtube_and_save_cookies


router = APIRouter()
API_TOKEN = os.getenv("CRON_SECRET_TOKEN")

def update_youtube_cookies_task():
    EMAIL = os.getenv("YOUTUBE_EMAIL")
    PASSWORD = os.getenv("YOUTUBE_PASSWORD")
    OUTPUT_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "cookies.txt")
    if EMAIL and PASSWORD:
        login_youtube_and_save_cookies(EMAIL, PASSWORD, OUTPUT_PATH)
    else:
        print("❌ No se puede actualizar cookies, faltan variables de entorno")

@router.post("/cookies/update")
async def update_cookies(request: Request, background_tasks: BackgroundTasks):
    token = request.headers.get("Authorization")
    if token != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    background_tasks.add_task(update_youtube_cookies_task)
    return {"status": "started", "message": "Actualización de cookies en proceso"}
