"""
Interfaz (contrato) del repositorio de documentos.
Define QUÉ operaciones existen, no CÓMO se implementan.
Principio: Dependency Inversion (SOLID - DIP).
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.domain.entities.document import Document


class DocumentRepository(ABC):
    """
    Contrato abstracto para la persistencia de documentos.
    Los servicios dependen de esta interfaz, nunca de la implementación concreta.
    """

    @abstractmethod
    async def save(self, document: Document) -> Document:
        """Persiste un documento y retorna la entidad con ID asignado."""
        ...

    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Document]:
        """Busca un documento por su identificador único."""
        ...

    @abstractmethod
    async def find_by_checksum(self, checksum: str) -> Optional[Document]:
        """Busca un documento por su checksum (para detección de duplicados)."""
        ...

    @abstractmethod
    async def find_all(self) -> list[Document]:
        """Retorna todos los documentos almacenados."""
        ...

    @abstractmethod
    async def update(self, id: str, data: dict) -> Optional[Document]:
        """Actualiza los campos de un documento existente."""
        ...

    @abstractmethod
    async def delete(self, id: str) -> None:
        """Elimina un documento por su ID."""
        ...