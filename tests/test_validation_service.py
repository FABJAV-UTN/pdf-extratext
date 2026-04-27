"""
Tests para ValidationService.
Metodología TDD: cada test define un comportamiento esperado.

Cobertura:
  - PDF válido → no lanza excepción
  - MIME inválido → InvalidPdfException
  - Archivo demasiado grande → InvalidPdfException
"""

import pytest
from unittest.mock import MagicMock

from app.application.services.validation_service import ValidationService
from app.core.exceptions import InvalidPdfException


# ─── Fixtures ────────────────────────────────────────────────────────────────

def make_mock_file(content_type: str, size: int = 1024):
    """Crea un mock de UploadFile con content_type y size configurables."""
    mock = MagicMock()
    mock.content_type = content_type
    mock.size = size
    return mock


@pytest.fixture
def service():
    return ValidationService()


@pytest.fixture
def valid_pdf_file():
    return make_mock_file(content_type="application/pdf", size=1024)


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestValidationService:

    def test_valid_pdf_does_not_raise(self, service, valid_pdf_file):
        """Un PDF válido y dentro del límite no debe lanzar excepción."""
        # No debe lanzar nada
        service.validate_pdf(valid_pdf_file)

    def test_invalid_mime_type_raises(self, service):
        """Un archivo que no es PDF debe lanzar InvalidPdfException."""
        mock_file = make_mock_file(content_type="image/jpeg")

        with pytest.raises(InvalidPdfException) as exc_info:
            service.validate_pdf(mock_file)

        assert "application/pdf" in str(exc_info.value)

    def test_file_exceeds_max_size_raises(self, service):
        """Un archivo que supera el tamaño máximo debe lanzar InvalidPdfException."""
        oversized_file = make_mock_file(
            content_type="application/pdf",
            size=20 * 1024 * 1024  # 20 MB > 10 MB por defecto
        )

        with pytest.raises(InvalidPdfException) as exc_info:
            service.validate_pdf(oversized_file)

        assert "tamaño máximo" in str(exc_info.value)

    def test_file_exactly_at_max_size_does_not_raise(self, service):
        """Un archivo exactamente en el límite máximo debe ser aceptado."""
        from app.core.config import settings
        edge_file = make_mock_file(
            content_type="application/pdf",
            size=settings.MAX_FILE_SIZE_BYTES
        )
        # No debe lanzar excepción
        service.validate_pdf(edge_file)

    def test_file_without_size_attribute_does_not_raise(self, service):
        """Si el archivo no tiene atributo 'size', no debe fallar."""
        mock_file = MagicMock()
        mock_file.content_type = "application/pdf"
        # Simular que no hay atributo size (algunos clientes no lo envían)
        del mock_file.size

        service.validate_pdf(mock_file)