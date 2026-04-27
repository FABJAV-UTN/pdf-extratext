# Guía de Módulos — Responsabilidades por Integrante

> Este documento describe **qué tiene que hacer cada persona**, qué archivos le pertenecen, qué reglas debe respetar y cómo se conecta con el trabajo del resto del equipo.

---

## Fabio — Líder · Lógica de Negocio + Dominio

**Archivos bajo tu responsabilidad:**
```
app/domain/entities/document.py
app/domain/interfaces/document_repository.py
app/application/services/document_service.py
app/application/services/pdf_service.py
app/application/services/validation_service.py
app/core/exceptions.py
tests/test_pdf_service.py
```

### Tu trabajo primero

Como líder, **definís el dominio antes que todos empiecen a codear**. Lu y Celina dependen de tus interfaces y entidades para poder trabajar. El orden recomendado:

1. Definir `Document` entity en `domain/entities/document.py`
2. Definir `DocumentRepository` (ABC) en `domain/interfaces/document_repository.py`
3. Definir las excepciones en `core/exceptions.py`
4. Implementar los services en `application/services/`

---

### `domain/entities/document.py`

La entidad central del sistema. Usar Pydantic v2 `BaseModel`.

```python
from pydantic import BaseModel, Field
from datetime import datetime

class Document(BaseModel):
    id: str | None = None
    filename: str
    checksum: str              # SHA-256 del binario del PDF
    text_content: str
    size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

**Regla:** esta clase no importa nada de FastAPI, MongoDB ni PyMuPDF. Es puro Python/Pydantic.

---

### `domain/interfaces/document_repository.py`

El contrato que Celina debe implementar. Define los métodos pero no la implementación.

```python
from abc import ABC, abstractmethod
from app.domain.entities.document import Document

class DocumentRepository(ABC):

    @abstractmethod
    async def save(self, document: Document) -> Document: ...

    @abstractmethod
    async def find_by_id(self, document_id: str) -> Document | None: ...

    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 20) -> list[Document]: ...

    @abstractmethod
    async def find_by_checksum(self, checksum: str) -> Document | None: ...

    @abstractmethod
    async def update(self, document_id: str, data: dict) -> Document | None: ...

    @abstractmethod
    async def delete(self, document_id: str) -> bool: ...

    @abstractmethod
    async def count(self) -> int: ...
```

**Regla:** no agregar ni quitar métodos sin coordinar con el equipo.

---

### `core/exceptions.py`

Excepciones de dominio que los services lanzan y los controllers capturan:

```python
class DocumentNotFoundError(Exception):
    """El documento solicitado no existe en la base de datos."""

class DuplicateDocumentError(Exception):
    """Ya existe un documento con el mismo checksum."""

class InvalidPDFError(Exception):
    """El archivo no es un PDF válido o está corrupto."""

class FileTooLargeError(Exception):
    """El archivo supera el tamaño máximo permitido."""
```

---

### `application/services/validation_service.py`

Valida los datos de entrada **antes** de cualquier procesamiento.

**Responsabilidades:**
- Verificar que los magic bytes del archivo son `%PDF` (los primeros 4 bytes).
- Verificar que `size_bytes <= MAX_FILE_SIZE_MB * 1024 * 1024`.
- Verificar que no existe un documento con el mismo checksum (llama al repositorio).

```python
import hashlib
from app.core.config import settings
from app.core.exceptions import InvalidPDFError, FileTooLargeError, DuplicateDocumentError
from app.domain.interfaces.document_repository import DocumentRepository

class ValidationService:

    async def validate_upload(self, content: bytes, repo: DocumentRepository) -> str:
        """Valida y retorna el checksum SHA-256 si todo es válido."""
        self._check_format(content)
        self._check_size(content)
        checksum = self._compute_checksum(content)
        await self._check_duplicate(checksum, repo)
        return checksum

    def _check_format(self, content: bytes) -> None:
        if not content.startswith(b"%PDF"):
            raise InvalidPDFError("El archivo no es un PDF válido.")

    def _check_size(self, content: bytes) -> None:
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if len(content) > max_bytes:
            raise FileTooLargeError(f"Tamaño máximo: {settings.MAX_FILE_SIZE_MB} MB.")

    def _compute_checksum(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    async def _check_duplicate(self, checksum: str, repo: DocumentRepository) -> None:
        existing = await repo.find_by_checksum(checksum)
        if existing:
            raise DuplicateDocumentError("El documento ya existe.")
```

---

### `application/services/pdf_service.py`

Extrae el texto del PDF **exclusivamente en memoria**.

```python
import fitz  # PyMuPDF
from io import BytesIO
from app.core.exceptions import InvalidPDFError

class PdfService:

    def extract_text(self, content: bytes) -> str:
        """Extrae todo el texto del PDF sin escribir a disco."""
        try:
            with fitz.open(stream=BytesIO(content), filetype="pdf") as doc:
                return "\n".join(page.get_text() for page in doc)
        except Exception as e:
            raise InvalidPDFError(f"Error al procesar el PDF: {e}")
```

**Regla crítica:** NUNCA usar `fitz.open("path/to/file.pdf")`. Siempre usar `stream=BytesIO(content)`.

---

### `application/services/document_service.py`

Orquesta toda la lógica de negocio. Es el único lugar donde se coordinan validación, extracción y persistencia.

```python
from app.domain.entities.document import Document
from app.domain.interfaces.document_repository import DocumentRepository
from app.application.services.pdf_service import PdfService
from app.application.services.validation_service import ValidationService
from app.core.exceptions import DocumentNotFoundError

class DocumentService:

    def __init__(self, repo: DocumentRepository, pdf_svc: PdfService, val_svc: ValidationService):
        self._repo = repo
        self._pdf = pdf_svc
        self._val = val_svc

    async def upload_document(self, filename: str, content: bytes) -> Document:
        checksum = await self._val.validate_upload(content, self._repo)
        text = self._pdf.extract_text(content)
        doc = Document(
            filename=filename,
            checksum=checksum,
            text_content=text,
            size_bytes=len(content)
        )
        return await self._repo.save(doc)

    async def get_document(self, document_id: str) -> Document:
        doc = await self._repo.find_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Documento {document_id} no encontrado.")
        return doc

    async def list_documents(self, skip: int = 0, limit: int = 20) -> tuple[list[Document], int]:
        docs = await self._repo.find_all(skip=skip, limit=limit)
        total = await self._repo.count()
        return docs, total

    async def update_document(self, document_id: str, data: dict) -> Document:
        doc = await self._repo.update(document_id, data)
        if not doc:
            raise DocumentNotFoundError(f"Documento {document_id} no encontrado.")
        return doc

    async def delete_document(self, document_id: str) -> None:
        deleted = await self._repo.delete(document_id)
        if not deleted:
            raise DocumentNotFoundError(f"Documento {document_id} no encontrado.")
```

---

### TDD — Tests que Fabio escribe

`tests/test_pdf_service.py`:
- `test_extract_text_valid_pdf` — PDF real pequeño en memoria → texto no vacío.
- `test_extract_text_invalid_bytes` → `InvalidPDFError`.
- `test_validate_upload_wrong_format` → `InvalidPDFError`.
- `test_validate_upload_too_large` → `FileTooLargeError`.
- `test_validate_upload_duplicate` → `DuplicateDocumentError`.
- `test_validate_upload_valid` → retorna checksum hex de 64 chars.

---

---

## Lu — Controladores + Integración (Presentación)

**Archivos bajo tu responsabilidad:**
```
app/presentation/controllers/document_controller.py
app/presentation/controllers/health_controller.py
app/presentation/schemas/document_schema.py
app/presentation/schemas/response_schema.py
app/presentation/routes.py
app/main.py
tests/test_documents.py
```

### Tu rol

Sos la capa que conecta HTTP con la lógica de negocio. Los controllers **no tienen lógica de negocio**, solo:
1. Reciben el request y lo deserializan.
2. Llaman al service correspondiente.
3. Formatean la respuesta con los schemas.
4. Capturan las excepciones del dominio y las mapean a HTTP errors.

---

### `presentation/schemas/document_schema.py`

```python
from pydantic import BaseModel
from datetime import datetime

class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    checksum: str
    text_content: str
    size_bytes: int
    created_at: datetime

class DocumentListItem(BaseModel):
    id: str
    filename: str
    checksum: str
    size_bytes: int
    created_at: datetime
    # Sin text_content — el listado es liviano

class DocumentUpdateRequest(BaseModel):
    filename: str
```

---

### `presentation/schemas/response_schema.py`

Wrapper genérico para todas las respuestas:

```python
from pydantic import BaseModel
from typing import Generic, TypeVar

T = TypeVar("T")

class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    message: str | None = None
```

---

### `presentation/controllers/document_controller.py`

```python
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from app.application.services.document_service import DocumentService
from app.core.exceptions import (
    DocumentNotFoundError, DuplicateDocumentError,
    InvalidPDFError, FileTooLargeError
)
from app.presentation.schemas.document_schema import (
    DocumentUploadResponse, DocumentListItem, DocumentUpdateRequest
)
from app.presentation.schemas.response_schema import ApiResponse

router = APIRouter(prefix="/documents", tags=["documents"])

# Mapeo de excepciones de dominio → HTTP status codes
EXCEPTION_MAP = {
    DocumentNotFoundError: 404,
    DuplicateDocumentError: 409,
    InvalidPDFError: 400,
    FileTooLargeError: 413,
}

@router.post("/upload", response_model=ApiResponse[DocumentUploadResponse], status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service)
):
    try:
        content = await file.read()
        doc = await service.upload_document(file.filename, content)
        return ApiResponse(success=True, data=DocumentUploadResponse(**doc.model_dump()), message="Documento subido exitosamente")
    except tuple(EXCEPTION_MAP.keys()) as e:
        raise HTTPException(status_code=EXCEPTION_MAP[type(e)], detail=str(e))
```

**Regla:** el `try/except` en el controller **solo captura excepciones de dominio** (las de `core/exceptions.py`). Cualquier otra cosa es un error 500 que FastAPI maneja automáticamente.

---

### `presentation/routes.py`

```python
from fastapi import APIRouter
from app.presentation.controllers.document_controller import router as document_router
from app.presentation.controllers.health_controller import router as health_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(document_router)
api_router.include_router(health_router)
```

---

### `main.py`

```python
from fastapi import FastAPI
from app.presentation.routes import api_router
from app.core.config import settings

app = FastAPI(title="PDF Document Manager", version="1.0.0")
app.include_router(api_router)
```

Acá también va el wiring de dependencias (ver sección de Inyección en `architecture.md`).

---

### TDD — Tests que Lu escribe

`tests/test_documents.py` (tests de integración con `TestClient` de FastAPI):
- `test_upload_valid_pdf_returns_201`
- `test_upload_non_pdf_returns_400`
- `test_upload_too_large_returns_413`
- `test_upload_duplicate_returns_409`
- `test_get_document_returns_200`
- `test_get_nonexistent_document_returns_404`
- `test_list_documents_returns_200`
- `test_update_document_returns_200`
- `test_delete_document_returns_200`
- `test_delete_nonexistent_document_returns_404`
- `test_health_check_returns_ok`

Todos los tests usan un `FakeDocumentRepository` (en memoria) inyectado via `app.dependency_overrides`. **No se conectan a MongoDB real.**

---

---

## Celina — Base de Datos + Persistencia (Infraestructura)

**Archivos bajo tu responsabilidad:**
```
app/infrastructure/database/mongo_client.py
app/infrastructure/repositories/document_repository_mongo.py
app/infrastructure/pdf/pdf_extractor.py     ← (solo si Fabio lo delega)
tests/test_repository.py
```

### Tu rol

Implementás los contratos que Fabio definió en el dominio. Tu código es el único que sabe que existe MongoDB. Si en el futuro se cambia a PostgreSQL, **solo tus archivos cambian**.

---

### `infrastructure/database/mongo_client.py`

```python
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings

_client: AsyncIOMotorClient | None = None

def get_mongo_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client

def get_database():
    return get_mongo_client()[settings.MONGO_DB_NAME]
```

**Regla:** usar un singleton para no abrir una conexión nueva por request.

---

### `infrastructure/repositories/document_repository_mongo.py`

Implementa **todos** los métodos del ABC `DocumentRepository`. No puede agregar métodos públicos extra.

```python
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from app.domain.entities.document import Document
from app.domain.interfaces.document_repository import DocumentRepository

class DocumentRepositoryMongo(DocumentRepository):

    def __init__(self, db: AsyncIOMotorDatabase):
        self._col = db["documents"]

    async def save(self, document: Document) -> Document:
        data = document.model_dump(exclude={"id"})
        result = await self._col.insert_one(data)
        document.id = str(result.inserted_id)
        return document

    async def find_by_id(self, document_id: str) -> Document | None:
        doc = await self._col.find_one({"_id": ObjectId(document_id)})
        return self._to_entity(doc) if doc else None

    async def find_all(self, skip: int = 0, limit: int = 20) -> list[Document]:
        cursor = self._col.find().sort("created_at", -1).skip(skip).limit(limit)
        return [self._to_entity(doc) async for doc in cursor]

    async def find_by_checksum(self, checksum: str) -> Document | None:
        doc = await self._col.find_one({"checksum": checksum})
        return self._to_entity(doc) if doc else None

    async def update(self, document_id: str, data: dict) -> Document | None:
        result = await self._col.find_one_and_update(
            {"_id": ObjectId(document_id)},
            {"$set": data},
            return_document=True
        )
        return self._to_entity(result) if result else None

    async def delete(self, document_id: str) -> bool:
        result = await self._col.delete_one({"_id": ObjectId(document_id)})
        return result.deleted_count == 1

    async def count(self) -> int:
        return await self._col.count_documents({})

    def _to_entity(self, doc: dict) -> Document:
        doc["id"] = str(doc.pop("_id"))
        return Document(**doc)
```

**Índices requeridos en MongoDB** (ejecutar una vez al iniciar la app o via script de setup):
```python
await db["documents"].create_index("checksum", unique=True)
await db["documents"].create_index([("created_at", -1)])
```

---

### TDD — Tests que Celina escribe

`tests/test_repository.py` usando `mongomock-motor` o un MongoDB de test:
- `test_save_document_returns_document_with_id`
- `test_save_duplicate_checksum_raises_error`
- `test_find_by_id_existing_document`
- `test_find_by_id_nonexistent_returns_none`
- `test_find_by_checksum_existing`
- `test_find_by_checksum_nonexistent_returns_none`
- `test_find_all_returns_list`
- `test_find_all_respects_skip_and_limit`
- `test_update_document_changes_filename`
- `test_delete_existing_document_returns_true`
- `test_delete_nonexistent_document_returns_false`
- `test_count_returns_correct_total`

---

---

## Roci — Frontend

**Archivos bajo tu responsabilidad:**
```
(Frontend separado del repo Python — puede ser una carpeta /frontend o un repo aparte)
```

### Tu rol

Crear la interfaz web que consuma la API definida en `api_contract.md`. El backend expone todo lo necesario — tu trabajo es construir el cliente.

### Endpoints que vas a usar

| Funcionalidad | Método | URL |
|---------------|--------|-----|
| Subir PDF | POST | `/api/v1/documents/upload` |
| Ver todos los documentos | GET | `/api/v1/documents` |
| Ver un documento | GET | `/api/v1/documents/{id}` |
| Editar nombre | PUT | `/api/v1/documents/{id}` |
| Eliminar | DELETE | `/api/v1/documents/{id}` |
| Estado del servicio | GET | `/api/v1/health` |

### Upload de archivo

El upload requiere `multipart/form-data`. El campo del archivo se llama `file`:

```javascript
const formData = new FormData();
formData.append("file", pdfFile);  // pdfFile es un objeto File del input

const response = await fetch("http://localhost:8000/api/v1/documents/upload", {
  method: "POST",
  body: formData,
  // No setear Content-Type manualmente — el browser lo hace con el boundary
});
```

### Manejo de errores esperados

| Status | Qué mostrarle al usuario |
|--------|--------------------------|
| 400 | "El archivo no es un PDF válido." |
| 409 | "Este documento ya fue subido anteriormente." |
| 413 | "El archivo es demasiado grande (máximo 10 MB)." |
| 404 | "El documento no existe." |
| 500 | "Error en el servidor. Intentá más tarde." |

### Estructura de respuesta

Todas las respuestas tienen el mismo formato:
```json
{ "success": true/false, "data": {...}, "message": "..." }
```

Siempre chequeá `response.success` antes de acceder a `response.data`.

---

---

## Orden de Trabajo Recomendado (para el equipo)

```
Semana 1
├── Fabio: Define domain/entities, domain/interfaces, core/exceptions
├── Todos: Revisan y aprueban el dominio (base del sistema)
│
Semana 2
├── Fabio:  Implementa services + tests unitarios (TDD)
├── Celina: Implementa mongo_client + repository + tests
├── Lu:     Implementa schemas + controllers (mockeando el service)
│
Semana 3
├── Lu:     Tests de integración con service real
├── Roci:   Frontend consumiendo la API
├── Todos:  Integration testing + review de código
│
Semana 4
├── Bug fixes, refactor, documentación final
└── Demo
```

---

## Reglas Globales del Equipo

1. **TDD**: escribir el test antes que la implementación.
2. **Sin lógica de negocio en controllers** — solo en services.
3. **Sin imports de infraestructura en application** — usar interfaces del dominio.
4. **Sin hardcoding** — toda configuración va en `core/config.py` y `.env`.
5. **El PDF nunca se escribe a disco** — siempre en memoria (`bytes` / `BytesIO`).
6. **Un PR por feature** — rama por tarea, revisión cruzada antes de mergear.
7. **GitHub Projects** — mover tarjetas: To Do → In Progress → In Review → Done.