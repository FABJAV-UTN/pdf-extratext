# Arquitectura del Sistema — PDF Document Manager

## Visión General

El sistema implementa una **arquitectura de 3 capas (N-Tier / Clean Architecture)** que separa responsabilidades entre presentación, lógica de negocio e infraestructura. Esto garantiza bajo acoplamiento, alta cohesión y facilidad para testear cada componente de forma aislada (TDD).

```
┌─────────────────────────────────────────────────────┐
│              CAPA DE PRESENTACIÓN                    │
│         FastAPI · Controllers · Schemas              │
│  (HTTP in/out — no business logic aquí)             │
├─────────────────────────────────────────────────────┤
│            CAPA DE APLICACIÓN                        │
│         Services · Use Cases · Validators            │
│  (Orquesta el dominio — no sabe de HTTP ni DB)      │
├─────────────────────────────────────────────────────┤
│                  DOMINIO                             │
│           Entities · Interfaces (ports)              │
│  (Reglas puras — sin dependencias externas)         │
├─────────────────────────────────────────────────────┤
│            CAPA DE INFRAESTRUCTURA                   │
│       MongoDB · PyMuPDF · Repositories               │
│  (Implementaciones concretas — detalles técnicos)   │
└─────────────────────────────────────────────────────┘
```

---

## Estructura de Directorios

```
project/
├── app/
│   ├── presentation/              # Capa de Presentación (HTTP)
│   │   ├── controllers/
│   │   │   ├── document_controller.py   # Endpoints CRUD de documentos
│   │   │   └── health_controller.py     # Health check del servicio
│   │   ├── schemas/               # DTOs — contratos HTTP de entrada/salida
│   │   │   ├── document_schema.py       # Request/Response de documentos
│   │   │   └── response_schema.py       # Wrapper de respuestas genéricas
│   │   └── routes.py              # Registro de todos los routers
│   │
│   ├── application/               # Capa de Aplicación (lógica de negocio)
│   │   └── services/
│   │       ├── document_service.py      # Orquesta operaciones CRUD
│   │       ├── pdf_service.py           # Extrae texto del PDF en memoria
│   │       └── validation_service.py    # Valida formato, tamaño, duplicados
│   │
│   ├── domain/                    # Dominio (reglas y contratos)
│   │   ├── entities/
│   │   │   └── document.py              # Entidad Document (Pydantic BaseModel)
│   │   └── interfaces/
│   │       └── document_repository.py   # Puerto (ABC) — contrato de persistencia
│   │
│   ├── infrastructure/            # Infraestructura (implementaciones concretas)
│   │   ├── repositories/
│   │   │   └── document_repository_mongo.py  # Implementa el puerto con Motor
│   │   ├── database/
│   │   │   └── mongo_client.py          # Conexión y cliente de MongoDB
│   │   └── pdf/
│   │       └── pdf_extractor.py         # Extrae texto con PyMuPDF (en memoria)
│   │
│   ├── core/
│   │   ├── config.py              # Variables de entorno (pydantic-settings)
│   │   └── exceptions.py          # Excepciones de dominio custom
│   │
│   └── main.py                    # Entrypoint — instancia FastAPI, registra routers
│
├── tests/
│   ├── test_documents.py          # Tests de integración de endpoints
│   ├── test_pdf_service.py        # Tests unitarios del servicio PDF
│   └── test_repository.py         # Tests del repositorio (mock de Motor)
│
├── docs/                          # Esta carpeta
├── pyproject.toml                 # Dependencias y configuración del proyecto (uv)
├── uv.lock
└── README.md
```

---

## Flujo de una Solicitud (Upload de PDF)

```
Cliente HTTP
    │
    ▼
[POST /documents/upload]
    │  UploadFile (multipart)
    ▼
document_controller.py
    │  Llama a DocumentService — pasa bytes, NO el archivo
    ▼
validation_service.py
    │  • ¿Es PDF válido? (magic bytes)
    │  • ¿Tamaño <= MAX_FILE_SIZE?
    │  • ¿Checksum ya existe en DB?  ←── llama al repositorio
    ▼
pdf_service.py
    │  • Extrae texto en memoria (PyMuPDF, sin escribir a disco)
    ▼
document_service.py
    │  • Crea entidad Document con checksum SHA-256
    │  • Llama al repositorio para persistir
    ▼
document_repository_mongo.py
    │  • Persiste en MongoDB
    ▼
Respuesta HTTP 201 con DocumentResponse
```

**Regla crítica:** el archivo PDF **nunca toca el disco**. Todo el procesamiento ocurre sobre los bytes crudos en memoria (`bytes` / `BytesIO`).

---

## Reglas de Dependencia (Dependency Rule)

Las dependencias **solo apuntan hacia adentro**:

```
presentation → application → domain ← infrastructure
```

- La capa de presentación importa de `application`.
- La capa de aplicación importa de `domain` (interfaces/entities).
- La infraestructura implementa los contratos del `domain`.
- **Nadie** importa de `presentation` ni de `infrastructure` directamente (excepto `main.py` para el wiring de dependencias).

### Inyección de Dependencias

`main.py` y FastAPI `Depends()` son los únicos lugares donde se ensamblan las implementaciones concretas:

```python
# Ejemplo en main.py / routes.py
def get_repository() -> DocumentRepository:
    return DocumentRepositoryMongo(mongo_client)

def get_document_service(repo = Depends(get_repository)) -> DocumentService:
    return DocumentService(repo, ValidationService(), PdfService())
```

Esto permite que los tests inyecten un repositorio falso (`FakeRepository`) sin tocar ningún servicio.

---

## Principios Aplicados

| Principio | Dónde se aplica |
|-----------|-----------------|
| **SRP** | Cada clase tiene una única razón para cambiar (service vs repository vs extractor) |
| **OCP** | Nuevo tipo de storage = nueva clase que implementa `DocumentRepository` |
| **LSP** | `DocumentRepositoryMongo` es sustituible por cualquier otra implementación |
| **ISP** | El repositorio expone solo los métodos que el dominio necesita |
| **DIP** | Application depende de la interfaz `DocumentRepository`, no de Motor |
| **DRY** | Checksum, validación de formato y límite de tamaño en un solo lugar |
| **KISS** | Sin abstracciones innecesarias — si no se necesita, no existe |
| **YAGNI** | No hay caché, queue, ni multi-tenant — el MVP no lo requiere |

---

## Factor 12-App

| Factor | Implementación |
|--------|----------------|
| **Codebase** | Un repo, múltiples entornos via variables de entorno |
| **Dependencies** | `pyproject.toml` + `uv.lock` — versiones fijadas |
| **Config** | `core/config.py` con `pydantic-settings` — nunca hardcodeado |
| **Backing services** | MongoDB como servicio adjunto via `MONGO_URI` |
| **Stateless** | Sin estado en memoria entre requests — todo en DB |
| **Logs** | `stdout` con `logging` estándar de Python |

---

## Tecnologías

| Componente | Tecnología | Versión mínima |
|-----------|------------|----------------|
| Framework web | FastAPI | 0.110+ |
| Servidor ASGI | Uvicorn | 0.29+ |
| ORM / driver DB | Motor (async MongoDB) | 3.3+ |
| Extracción PDF | PyMuPDF (`fitz`) | 1.24+ |
| Validación datos | Pydantic v2 | 2.6+ |
| Config entorno | pydantic-settings | 2.2+ |
| Testing | pytest + pytest-asyncio | latest |
| Package manager | uv | 0.1+ |

---

## Responsables por Capa

| Capa | Archivos | Responsable |
|------|----------|-------------|
| Presentación | `controllers/`, `schemas/`, `routes.py` | **Lu** |
| Aplicación | `services/` | **Fabio** (líder) |
| Dominio | `entities/`, `interfaces/` | **Fabio** (líder) |
| Infraestructura | `repositories/`, `database/`, `pdf/` | **Celina** |
| Frontend / Cliente | (fuera del scope de este repo) | **Roci** |

> **Nota:** Fabio como líder es el responsable final de que las interfaces del dominio sean correctas antes de que Lu y Celina empiecen a implementar. El dominio es el contrato que une todas las capas.