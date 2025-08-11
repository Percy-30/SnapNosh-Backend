import os
import logging

logger = logging.getLogger(__name__)

async def cleanup_file(filepath: str):
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Archivo temporal eliminado: {filepath}")
    except Exception as e:
        logger.error(f"Error eliminando archivo {filepath}: {e}")
