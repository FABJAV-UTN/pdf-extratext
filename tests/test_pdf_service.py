"""
Tests para PdfService.
Metodología TDD: los tests definen el comportamiento antes de la implementación.

Cobertura:
  - Extracción exitosa con pdfplumber
  - Fallback a PyMuPDF cuando pdfplumber no devuelve texto
  - Lanza PdfExtractionException si ninguna librería extrae texto
  - El cursor del archivo se reposiciona tras la lectura
"""

import io
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.services.pdf_service import PdfService
from app.core.exceptions import PdfExtractionException


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_mock_upload_file(content: bytes = b"%PDF-fake-content"):
    """
    Crea un mock asíncrono de UploadFile.
    read() y seek() son awaitables.
    """
    mock = MagicMock()
    mock.read = AsyncMock(return_value=content)
    mock.seek = AsyncMock()
    return mock


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def service():
    return PdfService()


@pytest.fixture
def mock_file():
    return make_mock_upload_file()


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestPdfService:

    @pytest.mark.asyncio
    async def test_extract_text_with_pdfplumber_success(self, service, mock_file):
        """
        Si pdfplumber extrae texto, debe retornarlo sin llamar a PyMuPDF.
        """
        expected_text = "Contenido del documento PDF de prueba."

        with patch.object(service, "_extract_with_pdfplumber", return_value=expected_text):
            result = await service.extract_text(mock_file)

        assert result == expected_text

    @pytest.mark.asyncio
    async def test_extract_text_falls_back_to_pymupdf(self, service, mock_file):
        """
        Si pdfplumber no extrae texto, debe usar PyMuPDF como fallback.
        """
        fallback_text = "Texto extraído con PyMuPDF."

        with (
            patch.object(service, "_extract_with_pdfplumber", return_value=""),
            patch.object(service, "_extract_with_pymupdf", return_value=fallback_text),
        ):
            result = await service.extract_text(mock_file)

        assert result == fallback_text

    @pytest.mark.asyncio
    async def test_extract_text_raises_when_no_text_found(self, service, mock_file):
        """
        Si ninguna librería extrae texto, debe lanzar PdfExtractionException.
        """
        with (
            patch.object(service, "_extract_with_pdfplumber", return_value=""),
            patch.object(service, "_extract_with_pymupdf", return_value="   "),
        ):
            with pytest.raises(PdfExtractionException):
                await service.extract_text(mock_file)

    @pytest.mark.asyncio
    async def test_file_seek_called_after_extraction(self, service, mock_file):
        """
        Tras la extracción, el cursor del archivo debe reposicionarse a 0.
        """
        with patch.object(service, "_extract_with_pdfplumber", return_value="Texto válido."):
            await service.extract_text(mock_file)

        mock_file.seek.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_extract_text_strips_whitespace(self, service, mock_file):
        """
        El texto extraído debe retornarse sin espacios/saltos al inicio y final.
        """
        with patch.object(service, "_extract_with_pdfplumber", return_value="  texto  \n"):
            result = await service.extract_text(mock_file)

        assert result == "texto"

    def test_pdfplumber_returns_empty_string_on_exception(self, service):
        """
        Si pdfplumber lanza una excepción interna, _extract_with_pdfplumber
        debe retornar string vacío (para activar el fallback).
        """
        with patch("pdfplumber.open", side_effect=Exception("Error interno")):
            result = service._extract_with_pdfplumber(b"bytes")

        assert result == ""

    def test_pymupdf_raises_extraction_exception_on_failure(self, service):
        """
        Si PyMuPDF falla, debe lanzar PdfExtractionException.
        """
        with patch("fitz.open", side_effect=Exception("PDF corrupto")):
            with pytest.raises(PdfExtractionException) as exc_info:
                service._extract_with_pymupdf(b"bytes")

        assert "PyMuPDF" in str(exc_info.value)