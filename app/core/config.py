"""
Configuración centralizada de la aplicación.
Principio 12-Factor App (Factor III: Config):
  - Toda configuración se lee de variables de entorno.
  - No hay valores sensibles hardcodeados.
  - Valores por defecto seguros para desarrollo local.
"""

import os


class Settings:
    """
    Configuraciones globales leídas desde el entorno.
    Uso: from app.core.config import settings
    """

    # --- API ---
    APP_NAME: str = os.getenv("APP_NAME", "pdf-extractext")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # --- Base de datos ---
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB_NAME: str = os.getenv("MONGO_DB_NAME", "pdf_extractext")

    # --- Restricciones de archivos ---
    # Tamaño máximo en bytes: 10 MB por defecto
    MAX_FILE_SIZE_BYTES: int = int(os.getenv("MAX_FILE_SIZE_BYTES", str(10 * 1024 * 1024)))

    # MIME type permitido
    ALLOWED_MIME_TYPE: str = "application/pdf"


# Instancia singleton accesible en toda la app
settings = Settings()