# Metodología TDD — Guía Práctica

> TDD (Test-Driven Development) es un **criterio de evaluación** del proyecto. Esta guía explica cómo aplicarlo correctamente en este stack.

---

## El ciclo TDD: Red → Green → Refactor

```
1. RED    → Escribís el test. Lo corrés. Falla (porque el código no existe aún).
2. GREEN  → Escribís el mínimo código necesario para que el test pase.
3. REFACTOR → Mejorás el código sin que los tests fallen.
```

**Nunca** escribas código de producción sin tener primero un test que lo requiera.

---

## Setup del entorno de testing

```toml
# pyproject.toml — dependencias de dev
[tool.uv.dev-dependencies]
pytest = ">=8.0"
pytest-asyncio = ">=0.23"
httpx = ">=0.27"          # TestClient async de FastAPI
mongomock-motor = ">=0.0.21"  # MongoDB en memoria para tests
```

```bash
# Instalar dependencias
uv sync

# Correr todos los tests
uv run pytest

# Correr con cobertura
uv run pytest --cov=app --cov-report=term-missing

# Correr solo un archivo
uv run pytest tests/test_pdf_service.py -v
```

Configuración en `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Ejemplo completo de ciclo TDD

### Objetivo: implementar `ValidationService._check_format()`

**Paso 1 — RED: escribir el test primero**

```python
# tests/test_pdf_service.py
import pytest
from app.application.services.validation_service import ValidationService
from app.core.exceptions import InvalidPDFError

def test_check_format_raises_on_non_pdf():
    """Archivos que no empiezan con %PDF deben fallar."""
    svc = ValidationService()
    with pytest.raises(InvalidPDFError):
        svc._check_format(b"este no es un pdf")

def test_check_format_passes_for_valid_pdf():
    """Archivos con magic bytes correctos deben pasar."""
    svc = ValidationService()
    svc._check_format(b"%PDF-1.4 contenido...")  # No lanza excepción
```

Corrés `pytest` → **falla** porque `ValidationService` no existe aún. ✅ (Eso es correcto en TDD)

**Paso 2 — GREEN: escribir el mínimo código**

```python
# app/application/services/validation_service.py
from app.core.exceptions import InvalidPDFError

class ValidationService:
    def _check_format(self, content: bytes) -> None:
        if not content.startswith(b"%PDF"):
            raise InvalidPDFError("El archivo no es un PDF válido.")
```

Corrés `pytest` → **pasa**. ✅

**Paso 3 — REFACTOR: mejorar si es necesario**

En este caso el código ya es simple y claro. No hay nada que refactorizar.

---

## Fake Repository para tests (patrón clave)

Para testear los services sin MongoDB, crear un repositorio falso en memoria:

```python
# tests/conftest.py o en el archivo de test

from app.domain.interfaces.document_repository import DocumentRepository
from app.domain.entities.document import Document

class FakeDocumentRepository(DocumentRepository):
    """Repositorio en memoria para tests — no toca MongoDB."""

    def __init__(self):
        self._store: dict[str, Document] = {}
        self._counter = 0

    async def save(self, document: Document) -> Document:
        self._counter += 1
        document.id = str(self._counter)
        self._store[document.id] = document
        return document

    async def find_by_id(self, document_id: str) -> Document | None:
        return self._store.get(document_id)

    async def find_all(self, skip: int = 0, limit: int = 20) -> list[Document]:
        docs = list(self._store.values())
        return docs[skip:skip + limit]

    async def find_by_checksum(self, checksum: str) -> Document | None:
        return next((d for d in self._store.values() if d.checksum == checksum), None)

    async def update(self, document_id: str, data: dict) -> Document | None:
        doc = self._store.get(document_id)
        if not doc:
            return None
        for k, v in data.items():
            setattr(doc, k, v)
        return doc

    async def delete(self, document_id: str) -> bool:
        if document_id in self._store:
            del self._store[document_id]
            return True
        return False

    async def count(self) -> int:
        return len(self._store)
```

**Uso en tests:**

```python
# tests/test_pdf_service.py
import pytest
from tests.conftest import FakeDocumentRepository
from app.application.services.document_service import DocumentService
from app.application.services.pdf_service import PdfService
from app.application.services.validation_service import ValidationService

@pytest.fixture
def service():
    return DocumentService(
        repo=FakeDocumentRepository(),
        pdf_svc=PdfService(),
        val_svc=ValidationService()
    )

@pytest.mark.asyncio
async def test_upload_duplicate_raises_error(service):
    pdf_bytes = b"%PDF-1.4 ..."  # PDF mínimo válido
    await service.upload_document("doc.pdf", pdf_bytes)
    
    with pytest.raises(DuplicateDocumentError):
        await service.upload_document("doc.pdf", pdf_bytes)
```

---

## Override de dependencias en tests de integración (Lu)

Para los tests de los endpoints, FastAPI permite reemplazar dependencias:

```python
# tests/test_documents.py
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import FakeDocumentRepository

fake_repo = FakeDocumentRepository()

def override_get_repository():
    return fake_repo

app.dependency_overrides[get_repository] = override_get_repository

client = TestClient(app)

def test_upload_valid_pdf_returns_201():
    pdf_content = b"%PDF-1.4 test content"
    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("test.pdf", pdf_content, "application/pdf")}
    )
    assert response.status_code == 201
    assert response.json()["success"] is True
    assert "id" in response.json()["data"]
```

---

## Cobertura mínima esperada

| Módulo | Cobertura objetivo |
|--------|--------------------|
| `application/services/` | 90%+ |
| `presentation/controllers/` | 85%+ |
| `infrastructure/repositories/` | 80%+ |
| `domain/` | 100% (son solo modelos e interfaces) |

---

## Checklist antes de hacer un PR

- [ ] Todos los tests existentes pasan (`uv run pytest`)
- [ ] El nuevo código tiene tests que lo cubren
- [ ] No hay lógica de negocio en controllers
- [ ] No hay imports de infraestructura en application
- [ ] El PDF no se escribe a disco en ningún path
- [ ] Las variables de entorno se leen desde `settings`
- [ ] El código tiene docstrings en clases y métodos públicos