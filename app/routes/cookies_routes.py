import os
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from app.services.youtube_cookie_updater import login_youtube_and_save_cookies
import boto3

router = APIRouter()
API_TOKEN = os.getenv("CRON_SECRET_TOKEN")

def upload_to_s3(filename, bucket, key):
    s3 = boto3.client('s3')
    s3.upload_file(filename, bucket, key)
    print(f"✅ Archivo subido a s3://{bucket}/{key}")

def update_youtube_cookies_task():
    EMAIL = os.getenv("YOUTUBE_EMAIL")
    PASSWORD = os.getenv("YOUTUBE_PASSWORD")
    OUTPUT_PATH = os.getenv("YOUTUBE_COOKIES_PATH", "cookies.txt")
    S3_BUCKET = os.getenv("S3_BUCKET_NAME")
    S3_KEY = os.getenv("S3_COOKIES_KEY", "cookies.txt")

    if EMAIL and PASSWORD:
        print(f"Ejecutando login para {EMAIL}, guardando en {OUTPUT_PATH}")
        login_youtube_and_save_cookies(EMAIL, PASSWORD, OUTPUT_PATH)
        print("Cookies actualizadas correctamente.")
        
        # Subir cookies a S3 si configurado
        if S3_BUCKET:
            upload_to_s3(OUTPUT_PATH, S3_BUCKET, S3_KEY)
    else:
        print("❌ No se puede actualizar cookies, faltan variables de entorno")

@router.post("/cookies/update")
async def update_cookies(request: Request, background_tasks: BackgroundTasks):
    token = request.headers.get("Authorization")
    if token != f"Bearer {API_TOKEN}":
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    background_tasks.add_task(update_youtube_cookies_task)
    return {"status": "started", "message": "Actualización de cookies en proceso"}