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
│   ├── whatsapp/          # cliente REAL de WhatsApp Cloud API (Meta), incl. descarga de media
│   ├── transcription/      # transcripción de audio REAL (OpenAI Whisper) — Fase 2
│   ├── calendar/           # interfaz + implementación REAL (Google Calendar) — Fase 3
│   ├── gps/                # interfaz abstracta (placeholder, sin proveedor aún)
│   └── email/              # interfaz abstracta (placeholder Gmail/Outlook)
├── ai/                    # cliente LLM desacoplado + loop del agente + extracción de comprobantes (visión)
└── tools/                 # catálogo de herramientas + implementaciones (llaman a services)
```

## 7. Qué es real y qué es placeholder en este commit

| Componente | Estado |
|---|---|
| Webhook de WhatsApp (verificación + recepción + envío de texto, descarga de media) | **Real**, contra Meta Cloud API. Requiere credenciales propias en `.env` para funcionar end-to-end. |
| Agente IA con tool calling | **Real**, usa el SDK oficial de Anthropic. Requiere `ANTHROPIC_API_KEY`. |
| Base de datos PostgreSQL + migraciones | **Real** (Alembic). |
| Gastos, tareas, usuarios, permisos, auditoría | **Real**, con tests. |
| Transcripción de audio (mensajes de voz) | **Real** (Fase 2), usa la API de Whisper de OpenAI. Requiere `OPENAI_API_KEY`; si falta, el bot responde indicándolo en vez de fallar en silencio o simular una transcripción. |
| Extracción de datos de comprobantes/boletas (OCR) | **Real** (Fase 2), usa la capacidad de visión de Claude (no un servicio de OCR aparte). Nunca inventa campos que no aparecen en la imagen; los deja en `null`. |
| Servicios técnicos (`service_orders`), clientes, máquinas | **Real** (Fase 2): modelos, servicios, tools de IA (`crear_servicio`, `actualizar_servicio`, `buscar_servicios`, `buscar_cliente`, `buscar_maquina`) y endpoints de lectura + páginas del panel web. |
| Mantenimiento preventivo y alertas | **Real** (Fase 3): `maintenance_records`, cálculo automático de la próxima fecha/horómetro según la regla configurada en cada máquina, y detección de máquinas atrasadas o próximas a vencer (`buscar_mantenimiento_pendiente`, endpoint `/api/reports/mantenimiento-pendiente`, tarjeta en el dashboard). |
| Reportes avanzados (por trabajador/proveedor/cliente/máquina/sucursal, por período) | **Real** (Fase 3), en `report_service.py`. |
| Exportación de reportes (CSV, Excel, PDF) | **Real** (Fase 3): CSV con la librería estándar, Excel con `openpyxl`, PDF con `reportlab`. Endpoint `/api/reports/gastos/export`. |
| Dashboard web | **Real** (Fase 3): página `/dashboard` con indicadores clave y gráficos de barras simples (CSS, sin librería de gráficos). |
| Google Calendar | **Real** (Fase 3), usa una cuenta de servicio de Google Workspace con delegación de dominio completo (`GoogleCalendarProvider`). Verifica disponibilidad antes de crear una reunión, tal como pide la sección 13 del brief. Requiere `GOOGLE_SERVICE_ACCOUNT_JSON` y que un administrador de Google Workspace haya autorizado esa cuenta de servicio — sin eso, `crear_reunion`/`consultar_calendario` fallan explícitamente en vez de simular una respuesta. No se pudo probar de punta a punta en este entorno de desarrollo por no contar con una cuenta de Google Workspace real; los tests usan un `CalendarProvider` de prueba inyectado (mismo patrón que WhatsApp/transcripción/visión). |
| GPS, Email | **Solo interfaces abstractas** (`integrations/gps`, `integrations/email`). No hay implementación concreta porque no se conoce el proveedor de GPS ni está definido el flujo de envío de correo (Fase 4). Ningún código simula una respuesta real. |
| Grúas | Aún no implementado (Fase 4) — no hay tablas ni tools todavía. |
| Almacenamiento permanente de archivos (fotos de comprobantes, audios) | **No implementado**: los archivos de WhatsApp se procesan al vuelo (transcripción/extracción) y se descartan; solo el resultado (texto/JSON) queda en `media_logs` para auditoría. No hay proveedor de almacenamiento (S3/GCS) configurado — ver riesgo en la sección 8. |
| Panel web | **Real**: login, dashboard, usuarios, gastos, tareas, servicios técnicos, clientes y máquinas, consumiendo la API REST real. |

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
   terceros salvo los proveedores de IA (Anthropic, OpenAI para transcripción), que solo
   reciben el contenido estrictamente necesario para interpretar el mensaje o leer la imagen,
   nunca credenciales ni datos de otros sistemas).
6. **Sin almacenamiento permanente de archivos**: las fotos de comprobantes y los audios de
   WhatsApp se procesan al vuelo y no se guardan (ver tabla de la sección 7). Esto es
   aceptable para el MVP de Fase 2 (lo que importa para el negocio — el gasto, sus datos — sí
   queda registrado), pero significa que si la extracción automática se equivoca, no hay
   forma de volver a mirar la imagen original. Antes de depender de esto en producción con
   volumen real, conviene agregar un `FileStorageProvider` (S3/GCS) — la interfaz de
   `media_logs` ya está pensada para poder agregarle una URL de almacenamiento después.
7. **Costo de la extracción de comprobantes**: cada foto de boleta implica una llamada a
   Claude con imagen (más cara que una llamada de solo texto). Aceptable en el volumen de un
   equipo técnico pequeño; monitorear costos si el volumen de fotos crece mucho.
8. **Google Calendar sin probar contra un Workspace real**: la integración es código real
   (no un mock), pero este entorno de desarrollo no tiene una cuenta de servicio de Google
   Workspace real para probarla de punta a punta. Antes de usarla en producción: (a) crear un
   proyecto en Google Cloud, (b) crear una cuenta de servicio con el scope
   `https://www.googleapis.com/auth/calendar`, (c) un administrador de Workspace debe
   autorizar esa cuenta de servicio para delegación de dominio completo, (d) cargar el JSON
   de credenciales en `GOOGLE_SERVICE_ACCOUNT_JSON`. Sin esto, las tools de calendario
   responden con un error claro en vez de simular disponibilidad o crear un evento falso.
9. **No hay recordatorios automáticos de mantenimiento por WhatsApp todavía**: la Fase 3
   agrega la *detección* de mantenimiento atrasado/próximo (tool, endpoint, dashboard), pero
   no un job programado que le escriba proactivamente al responsable — eso requeriría además
   una plantilla de WhatsApp aprobada por Meta (ver riesgo 1). Queda como trabajo futuro
   conectar la detección ya construida a un cron + `WhatsAppClient.send_template()`.

## 9. Plan de fases (resumen)

- **Fase 0** (este documento): arquitectura, modelo de datos, contratos de API, estructura.
- **Fase 1 (MVP)**: WhatsApp (texto), agente con tool calling, usuarios/roles/permisos,
  gastos, tareas, panel web mínimo.
- **Fase 2**: audio + transcripción (OpenAI Whisper), OCR de comprobantes (visión de Claude),
  servicios técnicos (`service_orders`), clientes, máquinas.
- **Fase 3 (implementada en este commit)**: mantenimiento preventivo + alertas, reportes
  avanzados (por trabajador/proveedor/cliente/máquina/sucursal, por período), exportación
  CSV/Excel/PDF, dashboard web, Google Calendar.
- **Fase 4**: correo electrónico, GPS, camionetas, grúas, almacenamiento permanente de
  archivos (S3/GCS), recordatorios proactivos de mantenimiento vía plantillas de WhatsApp.
- **Fase 5**: inteligencia empresarial (consultas analíticas agregadas, comparativas
  mensuales, resúmenes ejecutivos) — siempre basada en datos reales y trazable a registros.
