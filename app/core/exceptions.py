"""
Excepciones del dominio y la aplicación.
Centralizadas aquí para evitar duplicación (DRY) y facilitar el manejo
uniforme de errores en toda la aplicación (KISS).
"""


class AppException(Exception):
    """Base para todas las excepciones de la aplicación."""
    pass


class DuplicateDocumentException(AppException):
    """
    Se lanza cuando se intenta subir un documento que ya existe,
    detectado por checksum idéntico.
    HTTP equivalente: 409 Conflict
    """
    pass


class DocumentNotFoundException(AppException):
    """
    Se lanza cuando no se encuentra un documento por ID.
    HTTP equivalente: 404 Not Found
    """
    pass


class InvalidPdfException(AppException):
    """
    Se lanza cuando el archivo no es un PDF válido o supera el tamaño máximo.
    HTTP equivalente: 400 Bad Request
    """
    pass


class PdfExtractionException(AppException):
    """
    Se lanza cuando ocurre un error al extraer texto del PDF.
    HTTP equivalente: 422 Unprocessable Entity
    """
    pass