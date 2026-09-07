# Arquitectura — Jacobea AI

## 1. Visión

Jacobea AI no es un chatbot: es una **capa conversacional sobre un sistema de gestión
empresarial estructurado**. WhatsApp es la interfaz de entrada/salida; toda la lógica de
negocio vive en el backend, en funciones controladas ("tools") que el modelo de lenguaje
puede invocar. El LLM **nunca** escribe SQL ni toca la base de datos directamente.

```
WhatsApp (Meta Cloud API)
        │  webhook (HTTPS, firmado)
        ▼
   FastAPI backend
        │
        ├── Identificación de usuario (por teléfono) + permisos por rol
        │
        ├── Agente IA (app/ai/agent.py)
        │        │  usa tool calling (Anthropic Messages API)
        │        ▼
        │   Tools controladas (app/tools/*)
        │        │  únicamente estas funciones tocan la base de datos
        │        ▼
        ├── Servicios de dominio (app/services/*) ── reglas de negocio + auditoría
        │        ▼
        └── PostgreSQL (SQLAlchemy + Alembic)

   Panel web (Next.js) ── consume la misma API REST (app/api/routes/*)
```

## 2. Decisión: Python + FastAPI vs Node.js + TypeScript

Elegimos **Python + FastAPI**. Comparación:

| Criterio | Python + FastAPI | Node.js + TypeScript |
|---|---|---|
| Tool calling / schemas | Pydantic genera y valida JSON Schema de forma nativa — encaja 1:1 con la definición de herramientas del LLM | Requiere librerías adicionales (zod, etc.) para el mismo resultado |
| Ecosistema IA/datos | SDKs oficiales de Anthropic/OpenAI de primera clase, Whisper/OCR, pandas para reportes | Ecosistema más orientado a web; IA es "importada" |
| ORM/migraciones | SQLAlchemy + Alembic, maduro para modelos relacionales complejos | Prisma/TypeORM también maduros, comparable |
| Curva para no-programadores que mantendrán el proyecto | Sintaxis más legible para revisar reglas de negocio | Similar, pero requiere entender tipos avanzados de TS |
| Concurrencia I/O (webhooks) | asyncio + FastAPI, sobresaliente | Node es igualmente fuerte (es su punto fuerte histórico) |

Node.js es igualmente válido y sería la alternativa razonable si el equipo tuviera más
experiencia en TypeScript. Se elige Python porque el corazón del sistema (interpretación de
lenguaje natural, extracción de datos desde texto/audio/imágenes, reportes) es una carga de
trabajo tipo "datos + IA", donde el ecosistema Python reduce fricción, y porque Pydantic
unifica validación de API + definición de herramientas de IA en un solo lugar.

## 3. Principio: la IA nunca modifica la base de datos directamente

- El LLM recibe un **catálogo de herramientas** (JSON Schema) definido en `app/tools/registry.py`.
- Cada herramienta llama a una función de `app/services/*`, que aplica reglas de negocio,
  permisos y auditoría antes de tocar la base de datos vía SQLAlchemy.
- El LLM jamás genera SQL ni recibe acceso de conexión a la base de datos.
- Todo tool call queda registrado (quién, cuándo, con qué argumentos, qué resultado) en
  `audit_logs` cuando modifica datos.

## 4. Niveles de confirmación (sección 21 del brief)

Cada herramienta declara un `confirmation_level`:

- **Nivel 1 (automático)**: se ejecuta de inmediato (`crear_gasto` propio, `buscar_*`,
  `crear_tarea` para uno mismo, `completar_tarea` propia).
- **Nivel 2 (requiere confirmación)**: el agente NO ejecuta el tool call. Genera una
  `PendingAction` (tabla `pending_actions`), le explica al usuario qué va a hacer y espera
  una respuesta afirmativa antes de ejecutar (`actualizar_gasto`, `crear_tarea` asignada a
  un tercero).
- **Nivel 3 (autorización obligatoria)**: reservado para pagos, transferencias, eliminación
  definitiva y cambios contables críticos. No se implementa ninguna herramienta de nivel 3 en
  el MVP porque esas operaciones aún no existen en el sistema; el framework ya soporta el
  nivel para cuando se agreguen.

Esta lógica vive en `app/ai/agent.py::AgentSession._dispatch_tool_call` — es código, no una
instrucción de prompt, precisamente para que el modelo no pueda "saltarse" la regla.

## 5. Permisos por rol

Ver `docs/security.md` para la matriz completa. Resumen del mecanismo:

- Cada usuario tiene un `role` (enum `UserRole`).
- `app/core/permissions.py` define `ROLE_PERMISSIONS: dict[UserRole, set[Permission]]`.
- Cada endpoint REST y cada tool de IA declara qué `Permission` requiere
  (`require_permission(Permission.EXPENSES_READ_ALL)`), y además los servicios aplican
  filtros de alcance (p.ej. un técnico que llama `buscar_gastos` sin permiso "read_all"
  automáticamente solo ve sus propios gastos, sin importar lo que haya "pedido" en su
  mensaje de WhatsApp).
- Este doble control (a nivel de tool/endpoint y a nivel de query) es intencional: aunque el
  prompt del sistema le diga al modelo qué no debe hacer, la aplicación de permisos ocurre en
  código determinista.

## 6. Componentes por carpeta

```
backend/app/
├── main.py                # arranque FastAPI, registro de routers
├── core/                  # configuración, enums de permisos, settings desde .env
├── db/                    # sesión de SQLAlchemy, Base declarativa, seed de datos dev
├── models/                # entidades ORM (una tabla = un archivo)
├── schemas/               # Pydantic (request/response de la API REST)
├── services/              # lógica de negocio + auditoría (única capa que escribe en DB)
├── auth/                  # JWT para el panel web, dependencias de autenticación
├── api/routes/            # endpoints REST (consumidos por el panel web y para pruebas)
├── integrations/
│   ├── whatsapp/          # cliente REAL de WhatsApp Cloud API (Meta)
│   ├── gps/                # interfaz abstracta (placeholder, sin proveedor aún)
│   ├── calendar/           # interfaz abstracta (placeholder Google Calendar)
│   └── email/              # interfaz abstracta (placeholder Gmail/Outlook)
├── ai/                    # cliente LLM desacoplado + loop del agente
└── tools/                 # catálogo de herramientas + implementaciones (llaman a services)
```

## 7. Qué es real y qué es placeholder en este commit

| Componente | Estado |
|---|---|
| Webhook de WhatsApp (verificación + recepción + envío de texto) | **Real**, contra Meta Cloud API. Requiere credenciales propias en `.env` para funcionar end-to-end. |
| Agente IA con tool calling | **Real**, usa el SDK oficial de Anthropic. Requiere `ANTHROPIC_API_KEY`. |
| Base de datos PostgreSQL + migraciones | **Real** (Alembic). |
| Gastos, tareas, usuarios, permisos, auditoría | **Real**, con tests. |
| Transcripción de audio, OCR de boletas | **No implementado aún** (Fase 2). El webhook de WhatsApp ignora mensajes de audio/imagen en Fase 1 y responde indicando que aún no se procesan. |
| GPS, Google Calendar, Email | **Solo interfaces abstractas** (`integrations/gps`, `integrations/calendar`, `integrations/email`). No hay implementación concreta porque no se conoce el proveedor de GPS ni se definieron credenciales de Calendar/Email. Ningún código simula una respuesta real. |
| Grúas, máquinas, mantenimiento, clientes (módulos completos) | Modelos de datos ya definidos en el esquema (para no romper relaciones futuras), pero sin API ni tools en Fase 1. |
| Panel web | **Real**, mínimo: login, listado de usuarios, gastos y tareas, consumiendo la API REST real. |

## 8. Riesgos técnicos identificados

1. **Ventana de 24 horas de WhatsApp**: Meta solo permite mensajes de formato libre dentro de
   las 24 h posteriores al último mensaje del usuario; fuera de eso se requieren plantillas
   aprobadas. Recordatorios/alertas proactivas (mantenimiento, tareas) necesitarán plantillas
   de mensaje aprobadas por Meta — no implementado en Fase 1.
2. **Costos y límites del LLM**: cada mensaje puede implicar varias llamadas (loop de tool
   calling). Se debe limitar el número de iteraciones por mensaje (`MAX_TOOL_ITERATIONS`) para
   evitar loops costosos o infinitos.
3. **Ambigüedad de lenguaje natural**: "la 33" puede ser máquina o cliente. El agente debe
   preguntar cuando hay ambigüedad real (no debe adivinar). Se maneja con prompts + tools que
   devuelven "no encontrado / múltiples coincidencias" en lugar de adivinar.
2. **Concurrencia de conversación**: dos mensajes casi simultáneos del mismo usuario podrían
   crear una condición de carrera sobre `pending_actions`. Se usa una fila única por usuario
   con `UPDATE ... WHERE user_id = :id` transaccional.
4. **Seguridad del webhook**: Meta firma los payloads (`X-Hub-Signature-256`); el backend debe
   validarla con el `APP_SECRET`, o el endpoint queda abierto a payloads falsificados.
5. **PII y datos financieros**: los mensajes de WhatsApp y las transcripciones pueden contener
   información sensible. Se guardan en la base de datos de la empresa (no se reenvían a
   terceros salvo el proveedor del LLM, que solo recibe el texto necesario para interpretar
   la intención, nunca credenciales ni datos de otros sistemas).

## 9. Plan de fases (resumen)

- **Fase 0** (este documento): arquitectura, modelo de datos, contratos de API, estructura.
- **Fase 1 (MVP, implementada en este commit)**: WhatsApp (texto), agente con tool calling,
  usuarios/roles/permisos, gastos, tareas, panel web mínimo.
- **Fase 2**: audio + transcripción, OCR de comprobantes, servicios técnicos, clientes, máquinas.
- **Fase 3**: mantenimiento preventivo + alertas, reportes avanzados, dashboard, Excel/PDF,
  Google Calendar.
- **Fase 4**: correo electrónico, GPS, camionetas, grúas.
- **Fase 5**: inteligencia empresarial (consultas analíticas agregadas, comparativas
  mensuales, resúmenes ejecutivos) — siempre basada en datos reales y trazable a registros.
