"""
Tests para DocumentService.
Metodología TDD: tests primero, luego implementación.

Cobertura completa de casos de uso:
  - upload_document: éxito, duplicado, PDF inválido
  - get_document: encontrado, no encontrado
  - list_documents: lista vacía, con documentos
  - update_document: éxito, no encontrado
  - delete_document: éxito, no encontrado

Todos los colaboradores (repository, pdf_service, validation_service)
son mockeados para aislar la lógica de negocio.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.services.document_service import DocumentService
from app.domain.entities.document import Document
from app.core.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
    InvalidPdfException,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_repository():
    """Mock del DocumentRepository con todos los métodos async."""
    repo = MagicMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_checksum = AsyncMock()
    repo.find_all = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_pdf_service():
    """Mock del PdfService."""
    svc = MagicMock()
    svc.extract_text = AsyncMock(return_value="Contenido de prueba del documento.")
    return svc


@pytest.fixture
def mock_validation_service():
    """Mock del ValidationService (por defecto no lanza excepciones)."""
    svc = MagicMock()
    svc.validate_pdf = MagicMock()  # No hace nada = válido
    return svc


@pytest.fixture
def service(mock_repository, mock_pdf_service, mock_validation_service):
    """Instancia de DocumentService con dependencias mockeadas."""
    return DocumentService(
        repository=mock_repository,
        pdf_service=mock_pdf_service,
        validation_service=mock_validation_service,
    )


@pytest.fixture
def mock_upload_file():
    """Mock de UploadFile de FastAPI."""
    mock = MagicMock()
    mock.read = AsyncMock(return_value=b"%PDF-fake-content-for-testing")
    mock.seek = AsyncMock()
    mock.content_type = "application/pdf"
    mock.size = 1024
    return mock


def make_document(id="doc-123", content="Texto", checksum="abc123"):
    return Document(id=id, content=content, checksum=checksum)


# ─── Tests: upload_document ───────────────────────────────────────────────────

class TestUploadDocument:

    @pytest.mark.asyncio
    async def test_upload_success_returns_id_and_checksum(
        self, service, mock_upload_file, mock_repository
    ):
        """Un PDF válido y sin duplicado debe retornar document_id y checksum."""
        saved_doc = make_document(id="new-id-001", checksum="sha256abc")
        mock_repository.find_by_checksum.return_value = None
        mock_repository.save.return_value = saved_doc

        result = await service.upload_document(mock_upload_file)

        assert result["document_id"] == "new-id-001"
        assert result["checksum"] == "sha256abc"

    @pytest.mark.asyncio
    async def test_upload_calls_validation(
        self, service, mock_upload_file, mock_validation_service, mock_repository
    ):
        """Debe llamarse validate_pdf antes de cualquier otra operación."""
        mock_repository.find_by_checksum.return_value = None
        mock_repository.save.return_value = make_document()

        await service.upload_document(mock_upload_file)

        mock_validation_service.validate_pdf.assert_called_once_with(mock_upload_file)

    @pytest.mark.asyncio
    async def test_upload_calls_pdf_extraction(
        self, service, mock_upload_file, mock_pdf_service, mock_repository
    ):
        """Debe llamarse extract_text para obtener el contenido del PDF."""
        mock_repository.find_by_checksum.return_value = None
        mock_repository.save.return_value = make_document()

        await service.upload_document(mock_upload_file)

        mock_pdf_service.extract_text.assert_called_once_with(mock_upload_file)

    @pytest.mark.asyncio
    async def test_upload_raises_on_duplicate_checksum(
        self, service, mock_upload_file, mock_repository
    ):
        """Si ya existe un doc con el mismo checksum, debe lanzar DuplicateDocumentException."""
        mock_repository.find_by_checksum.return_value = make_document()

        with pytest.raises(DuplicateDocumentException):
            await service.upload_document(mock_upload_file)

    @pytest.mark.asyncio
    async def test_upload_raises_on_invalid_pdf(
        self, service, mock_upload_file, mock_validation_service
    ):
        """Si la validación falla, debe propagar InvalidPdfException."""
        mock_validation_service.validate_pdf.side_effect = InvalidPdfException("No es PDF")

        with pytest.raises(InvalidPdfException):
            await service.upload_document(mock_upload_file)

    @pytest.mark.asyncio
    async def test_upload_saves_document_with_correct_data(
        self, service, mock_upload_file, mock_repository, mock_pdf_service
    ):
        """El documento guardado debe tener el content extraído por PdfService."""
        expected_content = "Texto extraído del PDF."
        mock_pdf_service.extract_text.return_value = expected_content
        mock_repository.find_by_checksum.return_value = None
        mock_repository.save.return_value = make_document(content=expected_content)

        await service.upload_document(mock_upload_file)

        saved_arg = mock_repository.save.call_args[0][0]
        assert saved_arg.content == expected_content


# ─── Tests: get_document ──────────────────────────────────────────────────────

class TestGetDocument:

    @pytest.mark.asyncio
    async def test_get_existing_document_returns_document(
        self, service, mock_repository
    ):
        """Si el documento existe, debe retornarlo."""
        doc = make_document(id="doc-abc")
        mock_repository.find_by_id.return_value = doc

        result = await service.get_document("doc-abc")

        assert result.id == "doc-abc"

    @pytest.mark.asyncio
    async def test_get_nonexistent_document_raises(self, service, mock_repository):
        """Si el documento no existe, debe lanzar DocumentNotFoundException."""
        mock_repository.find_by_id.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.get_document("id-inexistente")


# ─── Tests: list_documents ────────────────────────────────────────────────────

class TestListDocuments:

    @pytest.mark.asyncio
    async def test_list_returns_all_documents(self, service, mock_repository):
        """Debe retornar la lista completa de documentos."""
        docs = [make_document(id="1"), make_document(id="2")]
        mock_repository.find_all.return_value = docs

        result = await service.list_documents()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_returns_empty_list_when_no_documents(
        self, service, mock_repository
    ):
        """Si no hay documentos, retorna lista vacía."""
        mock_repository.find_all.return_value = []

        result = await service.list_documents()

        assert result == []


# ─── Tests: update_document ───────────────────────────────────────────────────

class TestUpdateDocument:

    @pytest.mark.asyncio
    async def test_update_existing_document_returns_updated(
        self, service, mock_repository
    ):
        """Actualiza un documento existente y retorna la versión actualizada."""
        original = make_document(id="doc-1", content="Viejo contenido")
        updated = make_document(id="doc-1", content="Nuevo contenido")

        mock_repository.find_by_id.return_value = original
        mock_repository.update.return_value = updated

        result = await service.update_document("doc-1", "Nuevo contenido")

        assert result.content == "Nuevo contenido"
        mock_repository.update.assert_called_once_with("doc-1", {"content": "Nuevo contenido"})

    @pytest.mark.asyncio
    async def test_update_nonexistent_document_raises(self, service, mock_repository):
        """Si el documento no existe, debe lanzar DocumentNotFoundException."""
        mock_repository.find_by_id.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.update_document("id-fantasma", "contenido")


# ─── Tests: delete_document ───────────────────────────────────────────────────

class TestDeleteDocument:

    @pytest.mark.asyncio
    async def test_delete_existing_document_calls_repository(
        self, service, mock_repository
    ):
        """Eliminar un documento existente debe llamar a repository.delete."""
        mock_repository.find_by_id.return_value = make_document(id="doc-del")

        await service.delete_document("doc-del")

        mock_repository.delete.assert_called_once_with("doc-del")

    @pytest.mark.asyncio
    async def test_delete_nonexistent_document_raises(self, service, mock_repository):
        """Si el documento no existe, debe lanzar DocumentNotFoundException."""
        mock_repository.find_by_id.return_value = None

        with pytest.raises(DocumentNotFoundException):
            await service.delete_document("id-que-no-existe")