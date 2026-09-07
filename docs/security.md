# Seguridad y permisos

## Autenticación

- **Panel web**: JWT (access token corto, ~30 min) emitido en `POST /api/auth/login` con
  email + contraseña (bcrypt). Ver `app/auth/jwt.py`.
- **WhatsApp**: no hay "login" — el usuario se identifica por su número de teléfono
  (`telefono_whatsapp`), que debe estar previamente registrado por un administrador. Un
  número no registrado no puede usar ninguna función; el bot responde indicándolo y no
  procesa el mensaje con el LLM (para no gastar tokens ni exponer el agente a desconocidos).
- **Webhook de Meta**: se valida la firma `X-Hub-Signature-256` con `WHATSAPP_APP_SECRET`
  (HMAC-SHA256) en cada request entrante. El endpoint de verificación (`GET`) valida
  `hub.verify_token` contra `WHATSAPP_VERIFY_TOKEN`.

## Autorización — matriz de permisos por rol

Definida en `app/core/permissions.py`. Permisos (`Permission` enum):

- `EXPENSES_CREATE_OWN`, `EXPENSES_READ_OWN`, `EXPENSES_READ_ALL`, `EXPENSES_UPDATE_OWN`,
  `EXPENSES_UPDATE_ALL`, `EXPENSES_APPROVE_REIMBURSEMENT`
- `TASKS_CREATE_OWN`, `TASKS_ASSIGN_OTHERS`, `TASKS_READ_OWN`, `TASKS_READ_ALL`,
  `TASKS_COMPLETE_OWN`, `TASKS_COMPLETE_ALL`
- `USERS_READ_ALL`, `USERS_MANAGE`
- `REPORTS_VIEW_OWN`, `REPORTS_VIEW_ALL`
- `SERVICES_CREATE_OWN`, `SERVICES_READ_OWN`, `SERVICES_READ_ALL`, `SERVICES_UPDATE_OWN`,
  `SERVICES_UPDATE_ALL`, `SERVICES_ASSIGN`, `SERVICES_CLOSE` (Fase 2)
- `CUSTOMERS_READ`, `MACHINES_READ` (Fase 2)
- `MAINTENANCE_CREATE`, `MAINTENANCE_READ` (Fase 3)
- `CALENDAR_USE` (Fase 3)

| Rol | Permisos |
|---|---|
| `tecnico` | EXPENSES_CREATE_OWN, EXPENSES_READ_OWN, EXPENSES_UPDATE_OWN, TASKS_CREATE_OWN, TASKS_READ_OWN, TASKS_COMPLETE_OWN, REPORTS_VIEW_OWN, SERVICES_CREATE_OWN, SERVICES_READ_OWN, SERVICES_UPDATE_OWN, CUSTOMERS_READ, MACHINES_READ, MAINTENANCE_CREATE, MAINTENANCE_READ, CALENDAR_USE |
| `vendedor` | igual que técnico |
| `administracion` | EXPENSES_READ_ALL, EXPENSES_UPDATE_ALL, EXPENSES_APPROVE_REIMBURSEMENT, TASKS_READ_ALL, TASKS_ASSIGN_OTHERS, TASKS_COMPLETE_ALL, USERS_READ_ALL, REPORTS_VIEW_ALL, SERVICES_READ_ALL, SERVICES_UPDATE_ALL, + permisos de técnico |
| `jefe_servicios_tecnicos` | igual que administración (salvo EXPENSES_APPROVE_REIMBURSEMENT y USERS_READ_ALL) + SERVICES_ASSIGN, SERVICES_CLOSE |
| `gerente_sucursal` | todos los de administración, alcance limitado a su sucursal (filtrado en `services/`) |
| `gerente_marketing` | REPORTS_VIEW_OWN, TASKS_* propios (no financiero, sin acceso a gastos/servicios/clientes/máquinas/mantenimiento/calendario) |
| `responsable_mercado_publico` | permisos de técnico + REPORTS_VIEW_OWN |
| `gerente_general` | todos los permisos, sin restricción de sucursal |
| `admin_sistema` | todos los permisos + USERS_MANAGE (crear/editar usuarios y roles) |

La matriz completa está en código (`ROLE_PERMISSIONS`), no solo en este documento, para que
sea la fuente única de verdad verificable por tests (`tests/test_permissions.py`).

## Regla de oro: doble verificación

1. **A nivel de tool/endpoint**: `require_permission(...)` bloquea la operación completa si
   el usuario no tiene el permiso mínimo (ej. `EXPENSES_READ_ALL` para pedir el gasto de otra
   persona).
2. **A nivel de query**: incluso con el permiso mínimo (`EXPENSES_READ_OWN`), el servicio
   siempre filtra por `user_id` cuando el usuario no tiene el permiso "ALL" correspondiente.
   Esto significa que aunque alguien logre convencer al modelo de "ignorar las reglas", la
   query ejecutada en la base de datos sigue acotada por el backend.

Ejemplo concreto (sección 22 del brief): si un técnico le pide al bot "¿Cuánto gastó toda la
empresa este mes?", el tool `buscar_gastos` se ejecuta igual, pero el filtro de permisos
fuerza `user_id = <el técnico>` sin importar lo que haya escrito, y la IA responde con los
gastos del propio técnico junto con una nota de que no tiene acceso a información agregada de
la empresa.

## Niveles de confirmación de acciones

Ver `docs/architecture.md` §4 y `docs/ai-tools.md`. Implementado en código
(`app/tools/registry.py` + `app/ai/agent.py`), no delegado al prompt.

## Protección de secretos

- Todas las credenciales (WhatsApp, Anthropic, OpenAI, Google, base de datos, JWT secret) se
  leen desde variables de entorno vía `app/core/config.py` (Pydantic `BaseSettings`).
  `GOOGLE_SERVICE_ACCOUNT_JSON` en particular es un secreto muy sensible (permite actuar en
  nombre del calendario de cualquier usuario de Workspace vía delegación de dominio): tratarlo
  con el mismo cuidado que las credenciales de base de datos.
- `.env` está en `.gitignore`; `.env.example` documenta cada variable sin valores reales.
- Nunca se registra el contenido de tokens/secretos en logs.

## Rate limiting

El endpoint `/api/whatsapp/webhook` y `/api/auth/login` tienen limitación de tasa básica por
IP/número de teléfono (`slowapi`), para mitigar abuso y fuerza bruta. Configurable vía
`.env` (`RATE_LIMIT_*`).

## Validación de entradas

Todo payload de la API REST y del webhook pasa por esquemas Pydantic. Los argumentos que el
LLM entrega a una tool también se validan con Pydantic antes de tocar el servicio — si el
modelo entrega un tipo de dato incorrecto, la tool devuelve un error estructurado en vez de
ejecutar la operación.

## Auditoría

Toda escritura hecha por un tool de IA o por la API REST sobre `expenses`, `tasks`,
`users` queda en `audit_logs` con el estado anterior y nuevo, permitiendo responder
"quién creó/modificó qué y cuándo" (sección 19 del brief).

## HTTPS, ambientes y backups

- En producción, TLS se termina en el proveedor de despliegue (ver `docs/deployment.md`);
  la aplicación nunca debe exponerse por HTTP plano.
- Variables `ENVIRONMENT=development|staging|production` separan configuración (ver
  `.env.example`). Los datos de `development` son siempre ficticios (sección 33 del brief).
- Backups: se documenta en `docs/deployment.md` el mecanismo recomendado según el proveedor
  elegido (por ejemplo, backups automáticos diarios de Postgres en Railway/Render). No se
  implementa un mecanismo custom en el MVP.

## Qué NO hace el sistema (por diseño, en este estado)

- No envía correos externos automáticamente (sección 14): solo prepara borradores.
- No ejecuta pagos ni transferencias (nivel 3): no existen tools de ese tipo todavía.
- No borra información físicamente en entidades de negocio: usa soft delete.
- No inventa datos que no están en la base de datos ni en un comprobante adjunto.
