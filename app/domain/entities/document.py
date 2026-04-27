"""
Entidad de dominio: Document.
Representa el modelo central del sistema, sin dependencias externas.
Principio: Domain puro, sin acoplamiento a infraestructura (SOLID - DIP).
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Document:
    """
    Entidad central del dominio.
    Encapsula los datos de un documento PDF procesado.
    """
    content: str
    checksum: str
    id: Optional[str] = field(default=None)

    def has_id(self) -> bool:
        """Verifica si el documento ya fue persistido."""
        return self.id is not None