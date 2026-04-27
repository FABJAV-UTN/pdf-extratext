# Contrato de API — PDF Document Manager

> **Base URL:** `http://localhost:8000/api/v1`  
> **Content-Type default:** `application/json`  
> **Autenticación:** ninguna (MVP — etapa 1)

---

## Endpoints

### 1. Upload de documento PDF

**`POST /documents/upload`**

Recibe un archivo PDF, extrae su texto, calcula el checksum y persiste el documento.

**Request:**
```
Content-Type: multipart/form-data
Body: file (UploadFile) — archivo PDF
```

**Validaciones aplicadas (en orden):**
1. El archivo debe ser un PDF válido (magic bytes `%PDF`).
2. El tamaño no puede superar `MAX_FILE_SIZE` (configurable, default 10 MB).
3. El checksum SHA-256 no puede existir ya en la base de datos.
4. El archivo no se escribe a disco en ningún momento.

**Response 201 Created:**
```json
{
  "success": true,
  "data": {
    "id": "664f1a2b3c4d5e6f7a8b9c0d",
    "filename": "contrato.pdf",
    "checksum": "a3f5c2e1d4b7890abc123def456...",
    "text_content": "Texto extraído del PDF...",
    "size_bytes": 204800,
    "created_at": "2025-06-01T14:30:00Z"
  },
  "message": "Documento subido exitosamente"
}
```

**Errores posibles:**

| Código | Razón |
|--------|-------|
| `400` | Archivo no es un PDF válido |
| `413` | Archivo supera el tamaño máximo permitido |
| `409` | Documento duplicado (mismo checksum ya existe) |
| `422` | El campo `file` no fue enviado en el body |
| `500` | Error interno al procesar el PDF |

---

### 2. Obtener todos los documentos

**`GET /documents`**

Retorna la lista de todos los documentos persistidos.

**Query params opcionales:**

| Param | Tipo | Default | Descripción |
|-------|------|---------|-------------|
| `skip` | int | 0 | Paginación — cuántos registros omitir |
| `limit` | int | 20 | Paginación — máximo de resultados |

**Response 200 OK:**
```json
{
  "success": true,
  "data": [
    {
      "id": "664f1a2b3c4d5e6f7a8b9c0d",
      "filename": "contrato.pdf",
      "checksum": "a3f5c2e1d4b7890abc123def456...",
      "size_bytes": 204800,
      "created_at": "2025-06-01T14:30:00Z"
    }
  ],
  "total": 1,
  "message": null
}
```

> **Nota:** La lista **no incluye `text_content`** para aliviar el payload. Usar GET por ID para obtener el texto completo.

---

### 3. Obtener un documento por ID

**`GET /documents/{document_id}`**

Retorna el documento completo incluyendo el texto extraído.

**Path param:** `document_id` — ID de MongoDB (24 caracteres hex)

**Response 200 OK:**
```json
{
  "success": true,
  "data": {
    "id": "664f1a2b3c4d5e6f7a8b9c0d",
    "filename": "contrato.pdf",
    "checksum": "a3f5c2e1d4b7890abc123def456...",
    "text_content": "Texto extraído del PDF...",
    "size_bytes": 204800,
    "created_at": "2025-06-01T14:30:00Z"
  },
  "message": null
}
```

**Errores posibles:**

| Código | Razón |
|--------|-------|
| `404` | Documento no encontrado |
| `422` | `document_id` con formato inválido |

---

### 4. Actualizar metadata de un documento

**`PUT /documents/{document_id}`**

Permite actualizar el `filename` del documento. **No permite re-subir el PDF.**

**Request body:**
```json
{
  "filename": "nuevo_nombre.pdf"
}
```

**Response 200 OK:**
```json
{
  "success": true,
  "data": {
    "id": "664f1a2b3c4d5e6f7a8b9c0d",
    "filename": "nuevo_nombre.pdf",
    "checksum": "a3f5c2e1d4b7890abc123def456...",
    "size_bytes": 204800,
    "created_at": "2025-06-01T14:30:00Z"
  },
  "message": "Documento actualizado"
}
```

**Errores posibles:**

| Código | Razón |
|--------|-------|
| `404` | Documento no encontrado |
| `422` | Body inválido |

---

### 5. Eliminar un documento

**`DELETE /documents/{document_id}`**

Elimina el documento de la base de datos de forma permanente.

**Response 200 OK:**
```json
{
  "success": true,
  "data": null,
  "message": "Documento eliminado exitosamente"
}
```

**Errores posibles:**

| Código | Razón |
|--------|-------|
| `404` | Documento no encontrado |

---

### 6. Health Check

**`GET /health`**

Verifica que el servicio y la conexión a la base de datos están operativos.

**Response 200 OK:**
```json
{
  "status": "ok",
  "database": "connected"
}
```

**Response 503 Service Unavailable** (si MongoDB no responde):
```json
{
  "status": "degraded",
  "database": "disconnected"
}
```

---

## Esquema de Respuesta Genérico

Todos los endpoints (excepto `/health`) usan el mismo wrapper:

```json
{
  "success": true | false,
  "data": <objeto o lista o null>,
  "message": "string o null"
}
```

En caso de error, FastAPI retorna:
```json
{
  "success": false,
  "data": null,
  "message": "Descripción del error"
}
```

Los errores de validación de Pydantic (422) mantienen el formato estándar de FastAPI pero también se pueden uniformizar con un exception handler global.

---

## Modelo de Datos — Document

Estructura almacenada en MongoDB:

```
Colección: documents

{
  "_id": ObjectId,          ← ID de MongoDB
  "filename": string,       ← Nombre original del archivo
  "checksum": string,       ← SHA-256 del contenido binario del PDF (único)
  "text_content": string,   ← Texto extraído por PyMuPDF
  "size_bytes": int,        ← Tamaño en bytes
  "created_at": datetime    ← Timestamp UTC de creación
}

Índices:
  - checksum: único (garantiza no duplicados)
  - created_at: descendente (para queries paginadas)
```

---

## Variables de Entorno Requeridas

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB_NAME=pdf_manager
MAX_FILE_SIZE_MB=10
```

Todas las variables se definen en `app/core/config.py` y **nunca se hardcodean** en el código.

---

## Notas para el Equipo

- **Lu (Controladores):** Los controllers no deben contener lógica de validación ni de negocio. Su única responsabilidad es recibir el request, delegar al service, y devolver la respuesta formateada con el schema correcto.
- **Roci (Frontend):** Usar el header `Content-Type: multipart/form-data` para el upload. El campo del archivo debe llamarse exactamente `file`. Para los demás endpoints, `application/json`.
- **Fabio (Lógica):** El `document_service.py` es el único punto que orquesta validación + extracción + persistencia. Exponer métodos claros: `upload_document(filename, content: bytes)`, `get_document(id)`, `list_documents(skip, limit)`, `update_document(id, data)`, `delete_document(id)`.
- **Celina (DB):** El repositorio debe tener exactamente los métodos que define la interfaz en `domain/interfaces/document_repository.py`. No agregar métodos extra sin coordinarlo con Fabio.