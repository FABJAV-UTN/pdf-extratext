"""
ValidationService: valida que el archivo sea un PDF válido y esté dentro
del tamaño permitido.

Responsabilidades (según modules.md):
  - Validar formato PDF (tipo MIME)
  - Validar tamaño máximo permitido

Principios aplicados:
  - SRP (Single Responsibility): solo valida, no extrae ni persiste.
  - KISS: lógica directa sin sobre-ingeniería.
  - YAGNI: no agrega validaciones que no fueron pedidas.
"""

from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import InvalidPdfException


class ValidationService:
    """
    Servicio de validación de archivos PDF entrantes.
    """

    def validate_pdf(self, file: UploadFile) -> None:
        """
        Valida que el archivo sea PDF y no supere el tamaño máximo.

        Args:
            file: archivo subido via FastAPI.

        Raises:
            InvalidPdfException: si el archivo no es PDF o es demasiado grande.
        """
        self._validate_mime_type(file)
        self._validate_file_size(file)

    # --- Métodos privados (cohesión + legibilidad) ---

    def _validate_mime_type(self, file: UploadFile) -> None:
        """Verifica que el content-type sea application/pdf."""
        if file.content_type != settings.ALLOWED_MIME_TYPE:
            raise InvalidPdfException(
                f"Tipo de archivo no permitido: '{file.content_type}'. "
                f"Solo se aceptan PDFs ({settings.ALLOWED_MIME_TYPE})."
            )

    def _validate_file_size(self, file: UploadFile) -> None:
        """
        Verifica que el archivo no supere el tamaño máximo configurado.
        Nota: FastAPI no expone el size directamente en todos los casos;
        se delega la lectura del tamaño al caller si es necesario.
        Si el archivo tiene headers de tamaño (Content-Length), se verifica aquí.
        """
        # UploadFile puede tener size disponible si el cliente lo envía
        if hasattr(file, "size") and file.size is not None:
            if file.size > settings.MAX_FILE_SIZE_BYTES:
                raise InvalidPdfException(
                    f"El archivo supera el tamaño máximo permitido "
                    f"({settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)."
                )