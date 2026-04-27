"""
PdfService: extrae texto de archivos PDF en memoria.

Responsabilidades (según modules.md):
  - Extraer texto de PDF
  - No persistir archivos (procesamiento 100% en memoria)

Principios aplicados:
  - SRP: una sola responsabilidad, extracción de texto.
  - YAGNI: no implementa OCR avanzado si no fue pedido explícitamente.
  - KISS: intenta con pdfplumber primero, fallback a PyMuPDF.
  - 12-Factor: no escribe archivos temporales al disco.
"""

import io

import pdfplumber
import fitz  # PyMuPDF

from fastapi import UploadFile

from app.core.exceptions import PdfExtractionException


class PdfService:
    """
    Servicio de extracción de texto de PDFs.
    Todo el procesamiento ocurre en memoria (sin archivos temporales).
    """

    async def extract_text(self, file: UploadFile) -> str:
        """
        Extrae el texto completo de un archivo PDF.

        Estrategia:
          1. Intenta con pdfplumber (mejor para PDFs con texto embebido).
          2. Si falla o no hay texto, usa PyMuPDF como fallback.

        Args:
            file: archivo PDF subido via FastAPI.

        Returns:
            Texto extraído como string.

        Raises:
            PdfExtractionException: si no se puede extraer texto.
        """
        raw_bytes = await file.read()

        # Intentar con pdfplumber
        text = self._extract_with_pdfplumber(raw_bytes)

        # Fallback a PyMuPDF si pdfplumber no devuelve nada
        if not text.strip():
            text = self._extract_with_pymupdf(raw_bytes)

        if not text.strip():
            raise PdfExtractionException(
                "No se pudo extraer texto del PDF. "
                "El archivo podría estar escaneado sin OCR o estar vacío."
            )

        # Reposicionar el cursor para lecturas posteriores (checksum, etc.)
        await file.seek(0)

        return text.strip()

    # --- Métodos privados ---

    def _extract_with_pdfplumber(self, raw_bytes: bytes) -> str:
        """Extrae texto usando pdfplumber (recomendado para PDFs con texto nativo)."""
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                pages_text = [
                    page.extract_text() or ""
                    for page in pdf.pages
                ]
            return "\n".join(pages_text)
        except Exception:
            # Si pdfplumber falla, se intenta con el fallback
            return ""

    def _extract_with_pymupdf(self, raw_bytes: bytes) -> str:
        """Extrae texto usando PyMuPDF (fallback robusto)."""
        try:
            doc = fitz.open(stream=raw_bytes, filetype="pdf")
            pages_text = [page.get_text() for page in doc]
            doc.close()
            return "\n".join(pages_text)
        except Exception as e:
            raise PdfExtractionException(
                f"Error al procesar el PDF con PyMuPDF: {str(e)}"
            )