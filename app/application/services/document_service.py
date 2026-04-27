"""
DocumentService: orquestador central de la lógica de negocio.

Responsabilidades (según modules.md):
  - Orquestar el flujo de documentos
  - Validar duplicados (por checksum)
  - Calcular checksum del archivo
  - Delegar extracción a PdfService
  - Delegar persistencia al Repository

Principios aplicados:
  - SRP: orquesta, no implementa detalles técnicos.
  - DIP: depende de abstracciones (interfaces), no de implementaciones.
  - OCP: extensible via inyección de dependencias.
  - DRY: checksum calculado en un solo lugar (_calculate_checksum).
  - KISS: flujo lineal y legible.
"""

import hashlib

from fastapi import UploadFile

from app.domain.entities.document import Document
from app.domain.interfaces.document_repository import DocumentRepository
from app.application.services.pdf_service import PdfService
from app.application.services.validation_service import ValidationService
from app.core.exceptions import (
    DocumentNotFoundException,
    DuplicateDocumentException,
)


class DocumentService:
    """
    Servicio principal de negocio para la gestión de documentos PDF.
    Recibe sus dependencias por inyección (no las instancia internamente).
    """

    def __init__(
        self,
        repository: DocumentRepository,
        pdf_service: PdfService,
        validation_service: ValidationService,
    ) -> None:
        self._repository = repository
        self._pdf_service = pdf_service
        self._validation_service = validation_service

    # -------------------------------------------------------------------------
    # Casos de uso (uno por función pública)
    # -------------------------------------------------------------------------

    async def upload_document(self, file: UploadFile) -> dict:
        """
        Sube un documento PDF nuevo al sistema.

        Flujo:
          1. Validar que sea PDF y tamaño permitido
          2. Extraer texto en memoria
          3. Calcular checksum del archivo original
          4. Verificar que no sea duplicado
          5. Persistir documento
          6. Retornar id y checksum

        Args:
            file: archivo PDF subido via FastAPI.

        Returns:
            dict con 'document_id' y 'checksum'.

        Raises:
            InvalidPdfException: si el archivo no es válido.
            DuplicateDocumentException: si el checksum ya existe.
            PdfExtractionException: si no se puede extraer texto.
        """
        # 1. Validar formato y tamaño
        self._validation_service.validate_pdf(file)

        # 2. Extraer texto (en memoria)
        content = await self._pdf_service.extract_text(file)

        # 3. Calcular checksum del archivo raw
        checksum = await self._calculate_checksum(file)

        # 4. Detectar duplicado
        existing = await self._repository.find_by_checksum(checksum)
        if existing:
            raise DuplicateDocumentException(
                f"Ya existe un documento con checksum '{checksum}'."
            )

        # 5. Crear entidad y persistir
        document = Document(content=content, checksum=checksum)
        saved = await self._repository.save(document)

        # 6. Retornar respuesta según api_contract.md
        return {
            "document_id": saved.id,
            "checksum": saved.checksum,
        }

    async def get_document(self, id: str) -> Document:
        """
        Recupera un documento por ID.

        Args:
            id: identificador del documento.

        Returns:
            Entidad Document con id, content y checksum.

        Raises:
            DocumentNotFoundException: si no existe.
        """
        document = await self._repository.find_by_id(id)
        if not document:
            raise DocumentNotFoundException(
                f"No se encontró el documento con id '{id}'."
            )
        return document

    async def list_documents(self) -> list[Document]:
        """
        Lista todos los documentos disponibles.

        Returns:
            Lista de Documents (id y checksum según api_contract.md).
        """
        return await self._repository.find_all()

    async def update_document(self, id: str, content: str) -> Document:
        """
        Actualiza el contenido de un documento existente.

        Args:
            id: identificador del documento.
            content: nuevo contenido de texto.

        Returns:
            Document actualizado.

        Raises:
            DocumentNotFoundException: si no existe el documento.
        """
        # Verificar existencia antes de actualizar
        await self.get_document(id)

        updated = await self._repository.update(id, {"content": content})
        if not updated:
            raise DocumentNotFoundException(
                f"No se pudo actualizar el documento con id '{id}'."
            )
        return updated

    async def delete_document(self, id: str) -> None:
        """
        Elimina un documento por ID.

        Args:
            id: identificador del documento.

        Raises:
            DocumentNotFoundException: si no existe el documento.
        """
        # Verificar existencia antes de eliminar
        await self.get_document(id)
        await self._repository.delete(id)

    # -------------------------------------------------------------------------
    # Métodos privados
    # -------------------------------------------------------------------------

    async def _calculate_checksum(self, file: UploadFile) -> str:
        """
        Calcula el checksum SHA-256 del archivo en memoria.
        Reposiciona el cursor del archivo al inicio tras la lectura.

        Args:
            file: archivo cuyo checksum se calculará.

        Returns:
            String hexadecimal del hash SHA-256.
        """
        await file.seek(0)
        raw_bytes = await file.read()
        await file.seek(0)
        return hashlib.sha256(raw_bytes).hexdigest()