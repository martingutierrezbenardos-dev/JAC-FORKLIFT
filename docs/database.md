# Modelo de datos

Motor: **PostgreSQL**. ORM: **SQLAlchemy 2.x**. Migraciones: **Alembic**.

Convenciones globales (todas las tablas, vía `app/models/base.py::Base` y `TimestampMixin`):

- `id`: UUID v4, clave primaria.
- `created_at`, `updated_at`: timestamps con timezone, automáticos.
- `created_by`: FK a `users.id` cuando el registro lo crea una persona (nullable para datos
  de sistema/seed).
- Sin borrado físico de registros de negocio: `expenses`, `service_orders`,
  `maintenance_records` y `tasks` usan **soft delete** (`deleted_at` nullable). El resto de
  entidades de catálogo (customers, machines, users) también lo usan vía `activo`/`estado`.

## Entidades implementadas en Fase 1

### `users`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| nombre | str | |
| apellido | str | |
| telefono_whatsapp | str, único | formato E.164, ej `+56912345678`. Clave de identificación en WhatsApp. |
| email | str, único, nullable | |
| password_hash | str, nullable | solo para acceso al panel web (bcrypt). Los técnicos que solo usan WhatsApp pueden no tenerlo. |
| cargo | str | texto libre (ej. "Técnico senior") |
| area | str | |
| sucursal | str | |
| rol | enum `UserRole` | ver `docs/security.md` |
| activo | bool | default true |
| created_at / updated_at | timestamp | |

### `expenses` (gastos)
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| user_id | FK users | quién registra/incurre el gasto |
| fecha | date | |
| monto | numeric(14,2) | siempre positivo |
| moneda | enum (`CLP`, `USD`) | default `CLP` |
| categoria | enum `ExpenseCategory` | repuesto, combustible, peaje, alimentacion, alojamiento, transporte, herramientas, insumos, otros |
| proveedor | str, nullable | |
| descripcion | text, nullable | |
| cliente_id | FK customers, nullable | |
| maquina_id | FK machines, nullable | |
| proyecto_id | UUID, nullable | reservado (no hay tabla `projects` aún) |
| forma_pago | enum `PaymentMethod` | tarjeta_empresa, efectivo_propio, transferencia_empresa, otro |
| pagado_por | FK users, nullable | si es distinto de `user_id` (ej. alguien pagó por otro) |
| requiere_reembolso | bool | derivado de `forma_pago == efectivo_propio` salvo que se indique lo contrario |
| estado_reembolso | enum `ReimbursementStatus`, nullable | pendiente, enviado_a_contabilidad, aprobado, pagado, rechazado |
| comprobante_url | str, nullable | Fase 2 (adjuntos vía WhatsApp media API) |
| observaciones | text, nullable | |
| created_by | FK users | quién generó el registro (puede diferir de `user_id` si un admin lo carga por otro) |
| deleted_at | timestamp, nullable | soft delete |

### `tasks`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| titulo | str | |
| descripcion | text, nullable | |
| asignado_a | FK users | |
| creado_por | FK users | |
| fecha_limite | timestamp, nullable | |
| prioridad | enum `TaskPriority` | baja, media, alta |
| estado | enum `TaskStatus` | pendiente, en_progreso, completada, cancelada |
| proyecto | str, nullable | texto libre en Fase 1 |
| deleted_at | timestamp, nullable | |

### `audit_logs`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| usuario_id | FK users, nullable | nullable porque algunas acciones son del sistema |
| accion | str | `create`, `update`, `delete`, `tool_call` |
| entidad | str | nombre de tabla/entidad lógica |
| entidad_id | UUID, nullable | |
| datos_anteriores | JSONB, nullable | |
| datos_nuevos | JSONB, nullable | |
| canal | str | `whatsapp`, `web`, `system` |
| ip | str, nullable | solo aplica a canal `web` |
| created_at | timestamp | |

### `pending_actions`
Soporte del nivel de confirmación 2/3 (ver `architecture.md` §4). No estaba en el listado
original del brief, pero es necesaria para que las reglas de confirmación sean código real y
no una promesa del prompt.

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| user_id | FK users | quién debe confirmar |
| tool_name | str | herramienta pendiente de ejecutar |
| tool_input | JSONB | argumentos que el modelo propuso |
| summary_for_user | text | texto en español mostrado al usuario para pedir confirmación |
| status | enum (`pendiente`, `confirmada`, `cancelada`, `expirada`) | |
| created_at / resolved_at | timestamp | |

### `conversation_messages`
Historial corto de la conversación de WhatsApp por usuario, para dar contexto al LLM sin
tener que "confiar en su memoria" (principio fundamental del brief: la memoria vive en la
base de datos, no en el modelo).

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| user_id | FK users | |
| role | enum (`user`, `assistant`, `tool`) | |
| content | text | |
| created_at | timestamp | |

## Entidades modeladas para no romper relaciones futuras (esquema presente, sin API/tools en Fase 1)

Se crean ahora en el esquema (tablas mínimas) porque `expenses` ya referencia `cliente_id` y
`maquina_id`, y porque cambiar claves foráneas después de tener datos reales es más riesgoso
que definir la tabla mínima desde el día uno:

- `customers` (id, nombre, rut, direccion, comuna, ciudad, contacto, telefono, email,
  tipo_cliente, estado)
- `machines` (id, numero_interno, numero_serie, marca, modelo, tipo, cliente_id, horometro,
  fecha_ultimo_mantenimiento, fecha_proximo_mantenimiento, horas_proximo_mantenimiento,
  estado, ubicacion, observaciones)

No se crean todavía (se diseñarán en su fase correspondiente porque sus reglas de negocio
aún no están definidas con suficiente detalle): `service_orders`, `maintenance_records`,
`vehicles`, `gps_events`, `crane_contracts`, `crane_usage`, `attachments`.

## Diagrama de relaciones (Fase 1)

```
users ──< expenses >── customers
  │           │
  │           └──< machines
  │
  ├──< tasks (asignado_a)
  ├──< tasks (creado_por)
  ├──< pending_actions
  ├──< conversation_messages
  └──< audit_logs
```

## Migraciones

Alembic vive en `backend/alembic/`. La migración inicial (`0001_initial_schema.py`) crea
todas las tablas de Fase 1 más `customers`/`machines` (vacías). Para generar nuevas
migraciones tras modificar un modelo:

```bash
cd backend
alembic revision --autogenerate -m "descripcion_del_cambio"
alembic upgrade head
```

## Datos de prueba

`backend/app/db/seed.py` crea usuarios, clientes y máquinas ficticias de desarrollo (Juan y
Cristian técnicos, Marcela administración, Pedro gerente general; Cliente A/B/C; Máquinas
33/42/51), tal como pide la sección 33 del brief. Nunca usa datos reales de la empresa.
