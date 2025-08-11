from fastapi import APIRouter, HTTPException, Query
from app.services.cookie_manager import CookieManager

router = APIRouter()

@router.post("/cookies/export")
async def export_cookies(browser: str = Query("chrome", description="Nombre del navegador")):
    """
    Endpoint para exportar cookies automáticamente desde el navegador indicado.
    """
    cm = CookieManager()
    success = cm.auto_export_cookies(browser.lower())
    if success:
        return {"status": "success", "message": f"Cookies exportadas correctamente desde {browser}"}
    else:
        raise HTTPException(status_code=500, detail=f"No se pudo exportar cookies desde {browser}")