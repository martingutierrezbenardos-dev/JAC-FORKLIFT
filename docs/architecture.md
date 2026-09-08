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
│   ├── email/               # interfaz + implementación REAL (Gmail) — Fase 4
│   ├── storage/             # interfaz + implementación REAL de almacenamiento (S3) — Fase 4
│   ├── google_workspace.py  # credenciales compartidas por Calendar y Gmail (misma cuenta de servicio)
│   └── gps/                # interfaz abstracta (sin proveedor concreto: no se conoce cuál usa la empresa)
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
| Google Calendar | **Real** (Fase 3), usa una cuenta de servicio de Google Workspace con delegación de dominio completo (`GoogleCalendarProvider`). Verifica disponibilidad antes de crear una reunión, tal como pide la sección 13 del brief. Requiere `GOOGLE_SERVICE_ACCOUNT_JSON` y que un administrador de Google Workspace haya autorizado esa cuenta de servicio — sin eso, `crear_reunion`/`consultar_calendario` fallan explícitamente en vez de simular una respuesta. |
| Correo (Gmail) | **Real** (Fase 4), `GmailEmailProvider` reutiliza la misma cuenta de servicio de Calendar con scopes de Gmail. `preparar_correo` solo crea un borrador; `enviar_correo` es siempre nivel 2 (nunca se envía sin confirmación explícita, sección 14 del brief). |
| Almacenamiento permanente de archivos (fotos de comprobantes) | **Real** (Fase 4), `S3FileStorageProvider` (Amazon S3, boto3). Requiere `AWS_S3_BUCKET`; sin eso, la foto se procesa al vuelo y se descarta como en Fases 2/3, sin simular una URL. Los audios no se guardan permanentemente (solo su transcripción, ver sección 8 del brief). |
| Grúas (`crane_contracts`, `crane_usage`) | **Real** (Fase 4): registro de horas usadas por WhatsApp, consulta de horas contratadas/disponibles, alerta al 85% de uso. Crear un contrato es una acción administrativa (endpoint REST), no una tool de IA. |
| Vehículos (ficha) | **Real** (Fase 4): tabla `vehicles`, ficha consultable por WhatsApp y panel web. |
| GPS | **Solo interfaz abstracta** (`integrations/gps`), sin cambios desde la Fase 1: sigue sin conocerse el proveedor que usa la empresa. Las tools de GPS (`consultar_ubicacion_vehiculo`, etc.) existen y resuelven el vehículo, pero siempre responden "GPS aún no está configurado" hasta que se implemente un `GpsProvider` concreto — nunca se simula una ubicación falsa. |
| Panel web | **Real**: login, dashboard, usuarios, gastos, tareas, servicios técnicos, clientes, máquinas, vehículos, contratos de grúa y resumen ejecutivo, consumiendo la API REST real. |
| Comparativas de período y resumen ejecutivo | **Real** (Fase 5), `analytics_service.py`. No es una integración externa: agrega los mismos reportes de gastos/tareas/servicios/mantenimiento/grúas ya reales, comparando contra el período anterior de igual duración. `generar_resumen_ejecutivo` exige `REPORTS_VIEW_ALL` sin excepción (no existe una versión "propia" con sentido). |

Ninguna integración externa de este proyecto se probó de punta a punta contra la cuenta real
de la empresa (WhatsApp Business, Anthropic, OpenAI, Google Workspace, AWS) — todas requieren
credenciales que no existen en este entorno de desarrollo. Lo que sí se verificó en cada caso:
el código compila e importa correctamente, los tests cubren la lógica de negocio con dobles de
prueba inyectados en el mismo punto donde iría el cliente real (mismo patrón en las ocho
integraciones: WhatsApp, Anthropic, OpenAI, visión de Claude, Google Calendar, Gmail, S3 y
GPS), y cuando la credencial falta, el sistema responde con un mensaje claro en vez de fallar
en silencio o simular una respuesta.

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
6. **Almacenamiento de archivos parcial**: con `AWS_S3_BUCKET` configurado, las fotos de
   comprobantes quedan guardadas permanentemente (`expenses` puede llevar una
   `comprobante_url` real). Los **audios no se guardan** — solo su transcripción — porque el
   brief solo exige conservar la transcripción para auditoría (sección 8), no el archivo de
   voz en sí. Sin `AWS_S3_BUCKET`, las fotos se procesan al vuelo y se descartan, igual que en
   Fases 2/3.
7. **Costo de la extracción de comprobantes**: cada foto de boleta implica una llamada a
   Claude con imagen (más cara que una llamada de solo texto). Aceptable en el volumen de un
   equipo técnico pequeño; monitorear costos si el volumen de fotos crece mucho.
8. **Integraciones de Google (Calendar y Gmail) sin probar contra un Workspace real**: ambas
   son código real (no un mock), pero este entorno de desarrollo no tiene una cuenta de
   servicio de Google Workspace real para probarlas de punta a punta. Antes de usarlas en
   producción: (a) crear un proyecto en Google Cloud, (b) crear una cuenta de servicio con los
   scopes de Calendar (`.../auth/calendar`) y Gmail (`.../auth/gmail.compose`,
   `.../auth/gmail.send`, `.../auth/gmail.readonly`), (c) un administrador de Workspace debe
   autorizar esa cuenta de servicio para delegación de dominio completo, (d) cargar el JSON de
   credenciales en `GOOGLE_SERVICE_ACCOUNT_JSON`. Sin esto, las tools correspondientes
   responden con un error claro en vez de simular disponibilidad, un evento o un correo falso.
9. **No hay recordatorios automáticos de mantenimiento por WhatsApp todavía**: la Fase 3
   agrega la *detección* de mantenimiento atrasado/próximo (tool, endpoint, dashboard), pero
   no un job programado que le escriba proactivamente al responsable — eso requeriría además
   una plantilla de WhatsApp aprobada por Meta (ver riesgo 1). Queda como trabajo futuro
   conectar la detección ya construida a un cron + `WhatsAppClient.send_template()`.
10. **GPS sigue sin proveedor definido**: las tools de vehículos (`consultar_ubicacion_vehiculo`,
    `consultar_kilometraje_vehiculo`, `consultar_viajes_vehiculo`) existen y resuelven el
    vehículo por patente, pero `_get_gps_provider()` en `app/services/gps_service.py` lanza
    `GpsNotConfiguredError` a propósito — es el único punto que hay que tocar cuando la
    empresa defina su proveedor real (Wialon, Geotab, uno propio). No implementar un
    proveedor concreto sin saber cuál usa la empresa es una decisión, no un olvido.
11. **Envío de correo real**: `enviar_correo` es siempre nivel 2 en el agente (nunca se envía
    sin confirmación explícita), pero una vez confirmado, el envío es real e irreversible —
    no hay "deshacer" un correo ya enviado por Gmail. Cualquier ampliación futura de esta
    tool debe mantener esa confirmación obligatoria.
12. **Costo de N consultas en el resumen ejecutivo**: `generar_resumen_ejecutivo` ejecuta
    varios reportes agregados en secuencia (gastos actual/anterior, tareas, servicios,
    mantenimiento, grúas). Con el volumen de datos de una empresa mediana esto es rápido, pero
    si el histórico de `expenses`/`service_orders` crece mucho, cada reporte itera todos los
    registros del período en Python (mismo patrón que `report_service` desde la Fase 1) — no
    hay agregación a nivel de SQL todavía. Optimizar solo si se vuelve un problema real
    (medir antes de optimizar).

## 9. Plan de fases (resumen)

- **Fase 0** (este documento): arquitectura, modelo de datos, contratos de API, estructura.
- **Fase 1 (MVP)**: WhatsApp (texto), agente con tool calling, usuarios/roles/permisos,
  gastos, tareas, panel web mínimo.
- **Fase 2**: audio + transcripción (OpenAI Whisper), OCR de comprobantes (visión de Claude),
  servicios técnicos (`service_orders`), clientes, máquinas.
- **Fase 3**: mantenimiento preventivo + alertas, reportes avanzados
  (por trabajador/proveedor/cliente/máquina/sucursal, por período), exportación CSV/Excel/PDF,
  dashboard web, Google Calendar.
- **Fase 4 (implementada en este commit)**: correo electrónico real (Gmail), grúas
  (contratos, uso, alerta de horas), vehículos (ficha) y almacenamiento permanente de
  comprobantes (S3). GPS queda con la misma interfaz abstracta de la Fase 1 — sigue sin
  implementarse un proveedor concreto porque no se conoce cuál usa la empresa. Recordatorios
  proactivos de mantenimiento vía plantillas de WhatsApp: no implementado (ver riesgo 9).
- **Fase 5 (implementada en este commit)**: inteligencia empresarial — comparativas de
  período contra período anterior (`comparar_periodo`) y resumen ejecutivo cruzando gastos,
  tareas, servicios, mantenimiento y grúas (`generar_resumen_ejecutivo`). No agrega ninguna
  integración externa nueva ni ninguna tabla: es una capa de agregación sobre los mismos
  `report_service`/`maintenance_service`/`crane_service` ya existentes, siempre trazable a
  IDs de registros reales (`registros_usados`), nunca una cifra inventada por el LLM.
