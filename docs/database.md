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

## Entidades implementadas

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

### `customers`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| nombre | str | |
| rut | str, único, nullable | |
| direccion, comuna, ciudad | str, nullable | |
| contacto | str, nullable | nombre de la persona de contacto |
| telefono, email | str, nullable | |
| tipo_cliente | str, nullable | texto libre (ej. "empresa", "particular") |
| estado | str | default `activo` |

### `machines`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| numero_interno | str, único | el identificador que usan los técnicos (ej. "33") |
| numero_serie, marca, modelo, tipo | str, nullable | |
| cliente_id | FK customers, nullable | dónde está instalada actualmente |
| horometro | int, nullable | Fase 3 lo mantendrá actualizado automáticamente vía mantenimiento |
| estado | str | default `operativa` |
| ubicacion, observaciones | str/text, nullable | |

Los campos de mantenimiento (`fecha_ultimo_mantenimiento`, `fecha_proximo_mantenimiento`,
`horas_proximo_mantenimiento`) del diseño original del brief se agregan en Fase 3 junto con
`maintenance_records`, para no crear columnas que ningún flujo llena todavía.

### `service_orders` (órdenes de servicio técnico) — Fase 2
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| numero | str, único | generado desde la secuencia `service_order_number_seq`, formato `OT-000123` |
| cliente_id | FK customers, nullable | |
| maquina_id | FK machines, nullable | |
| tecnico_id | FK users | quién atiende el servicio |
| fecha | date | fecha de creación de la orden |
| hora_salida / hora_llegada / hora_inicio / hora_termino | timestamp, nullable | reportados progresivamente por WhatsApp |
| motivo | text, nullable | por qué se generó la visita |
| diagnostico, trabajo_realizado, repuestos_utilizados, resultado | text, nullable | |
| estado | enum `ServiceOrderStatus` | pendiente, asignado, en_ruta, en_servicio, terminado, cerrado, cancelado |
| observaciones | text, nullable | |
| deleted_at | timestamp, nullable | soft delete |

### `media_logs` — Fase 2
Auditoría de cada archivo multimedia recibido por WhatsApp (sección 8 del brief: "la
transcripción debe conservarse opcionalmente para auditoría"). El archivo en sí **no** se
guarda de forma permanente — ver `architecture.md` §7 y §8 (riesgo de almacenamiento).

| Campo | Tipo | Notas |
|---|---|---|
| id | UUID | PK |
| user_id | FK users | |
| wa_media_id | str | referencia del archivo en Meta (temporal) |
| media_type | enum (`audio`, `image`, `document`) | |
| mime_type | str, nullable | |
| transcript | text, nullable | resultado de transcripción (audio) |
| extracted_data | JSONB, nullable | resultado de extracción (imagen/comprobante) |
| error | text, nullable | si el procesamiento falló |

## Entidades aún no creadas (fases futuras)

Sus reglas de negocio no están definidas con suficiente detalle todavía: `maintenance_records`
(Fase 3), `vehicles`, `gps_events`, `crane_contracts`, `crane_usage` (Fase 4), `attachments`
como tabla genérica de almacenamiento permanente de archivos (Fase 4, junto con un
`FileStorageProvider` real).

## Diagrama de relaciones

```
users ──< expenses >── customers
  │           │
  │           └──< machines >── customers
  │
  ├──< service_orders >── customers
  ├──< service_orders >── machines
  ├──< tasks (asignado_a)
  ├──< tasks (creado_por)
  ├──< pending_actions
  ├──< conversation_messages
  ├──< media_logs
  └──< audit_logs
```

## Migraciones

Alembic vive en `backend/alembic/`. Migraciones aplicadas:

- `0001_initial_schema.py`: usuarios, gastos, tareas, `customers`/`machines` (vacías),
  auditoría, acciones pendientes, mensajes de conversación (Fase 1).
- `0002_fase2_servicios_tecnicos.py`: `service_orders` (+ secuencia
  `service_order_number_seq` para el número de OT), `media_logs` (Fase 2).

Para generar nuevas migraciones tras modificar un modelo:

```bash
cd backend
alembic revision --autogenerate -m "descripcion_del_cambio"
alembic upgrade head
```

## Datos de prueba

`backend/app/db/seed.py` crea usuarios, clientes y máquinas ficticias de desarrollo (Juan y
Cristian técnicos, Marcela administración, Pedro gerente general; Cliente A/B/C; Máquinas
33/42/51, dos de ellas asociadas a un cliente para poder probar las relaciones), tal como pide
la sección 33 del brief. Nunca usa datos reales de la empresa.
