# Jacobea AI

IA conversacional de gestión interna para **Jacobea Forklift Chile**. Los trabajadores
escriben (o, en fases futuras, hablan) por WhatsApp y el sistema transforma esos mensajes en
registros estructurados de gastos, tareas y consultas — sin planillas ni formularios.

Este README está escrito para que lo pueda seguir alguien que no programa. Si algo no queda
claro, revisa `docs/` (hay un documento por tema) antes de tocar código.

## 1. ¿Qué hace el sistema hoy (Fase 1 — MVP)?

- Un trabajador registrado le escribe por WhatsApp cosas como *"Compré un rodamiento en
  Repuestos X, 85 lucas, plata mía"* y el sistema registra automáticamente el gasto.
- Se puede preguntar *"¿Cuánto he gastado este mes?"* o *"¿Qué tareas tengo pendientes?"* y
  el sistema responde con datos reales de la base de datos (nunca inventados).
- Cada rol (técnico, vendedor, administración, gerencia, etc.) ve solo la información que le
  corresponde — un técnico no puede ver el gasto total de la empresa, por ejemplo.
- Acciones sensibles (modificar un gasto, asignarle una tarea a otra persona) piden
  confirmación explícita antes de ejecutarse.
- Hay un panel web mínimo para ver usuarios, gastos y tareas desde el navegador.

Lo que **todavía no existe** (y por qué) está documentado en
`docs/architecture.md` (sección "Qué es real y qué es placeholder").

## 2. Arquitectura (resumen)

```
WhatsApp (Meta Cloud API) → Backend (FastAPI) → Agente de IA (Claude, tool calling)
                                    │
                                    ├── Servicios de negocio + permisos + auditoría
                                    └── PostgreSQL

Panel web (Next.js) ── consume la misma API REST del backend
```

El LLM **nunca** modifica la base de datos directamente: solo puede pedir que se ejecute una
de las "herramientas" controladas por el backend (crear un gasto, buscar tareas, etc.). El
detalle completo está en `docs/architecture.md`, `docs/database.md` y `docs/ai-tools.md`.

## 3. Estructura del proyecto

```
JAC-FORKLIFT/
├── backend/            FastAPI (Python) — API, agente de IA, tools, base de datos
│   ├── app/
│   │   ├── main.py
│   │   ├── core/               configuración, permisos, seguridad
│   │   ├── db/                 sesión de base de datos, seed de datos de prueba
│   │   ├── models/              tablas (SQLAlchemy)
│   │   ├── schemas/             validación de datos (Pydantic)
│   │   ├── services/            lógica de negocio + auditoría
│   │   ├── auth/                 JWT y dependencias de autenticación
│   │   ├── api/routes/           endpoints REST + webhook de WhatsApp
│   │   ├── integrations/         WhatsApp (real), GPS/Calendar/Email (placeholders)
│   │   ├── ai/                   cliente LLM + loop del agente
│   │   └── tools/                catálogo de herramientas del agente
│   ├── alembic/                  migraciones de base de datos
│   └── tests/                    pruebas automatizadas (pytest)
├── frontend/            Next.js (TypeScript) — panel web mínimo
├── docs/                 documentación detallada por tema
├── docker-compose.yml
├── .env.example
└── README.md
```

## 4. Requisitos previos

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (local o vía Docker)
- Una cuenta de Anthropic con una API key (para el agente de IA)
- Una cuenta de Meta Business con WhatsApp Cloud API configurada (para producción real; no
  es necesaria para desarrollar o correr los tests)

## 5. Instalación paso a paso (desarrollo local, sin Docker)

### 5.1 Base de datos

```bash
# Instala PostgreSQL si no lo tienes, luego crea el usuario y las bases de datos:
sudo -u postgres psql -c "CREATE USER jacobea WITH PASSWORD 'jacobea' SUPERUSER;"
sudo -u postgres psql -c "CREATE DATABASE jacobea_dev OWNER jacobea;"
sudo -u postgres psql -c "CREATE DATABASE jacobea_test OWNER jacobea;"  # para los tests
```

### 5.2 Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env
# Edita backend/.env: como mínimo, ANTHROPIC_API_KEY para que el agente de IA funcione.

alembic upgrade head              # crea todas las tablas
python -m app.db.seed             # carga usuarios/clientes/máquinas de prueba (ficticios)

uvicorn app.main:app --reload --port 8000
```

El backend queda disponible en `http://localhost:8000`. Puedes verificar que está vivo en
`http://localhost:8000/health`.

Usuarios de prueba creados por el seed (contraseña `dev12345` para quienes tienen acceso al
panel web):

| Nombre | Rol | Teléfono WhatsApp | Email (panel web) |
|---|---|---|---|
| Pedro Gerente | Gerente General | +56900000001 | pedro.gerente@jacobea-dev.cl |
| Marcela Administración | Administración | +56900000002 | marcela.admin@jacobea-dev.cl |
| Juan Técnico | Técnico | +56900000003 | (solo WhatsApp, sin acceso al panel) |
| Cristian Técnico | Técnico | +56900000004 | (solo WhatsApp, sin acceso al panel) |

### 5.3 Frontend (panel web)

```bash
cd frontend
npm install
cp .env.example .env.local        # NEXT_PUBLIC_API_URL debe apuntar al backend
npm run dev
```

Panel disponible en `http://localhost:3000`. Inicia sesión con uno de los emails de la tabla
anterior.

### 5.4 Con Docker Compose (alternativa)

```bash
cp .env.example backend/.env      # completa ANTHROPIC_API_KEY como mínimo
docker compose up --build
```

Esto levanta PostgreSQL, el backend y el frontend juntos. La primera vez, corre las
migraciones y el seed dentro del contenedor del backend:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.db.seed
```

## 6. Cómo correr los tests

```bash
cd backend
source .venv/bin/activate
# Los tests usan la base de datos jacobea_test (creada en el paso 5.1) y le aplican las
# migraciones una vez:
DATABASE_URL="postgresql+psycopg://jacobea:jacobea@localhost:5432/jacobea_test" alembic upgrade head
pytest
```

Los tests no requieren una `ANTHROPIC_API_KEY` real ni credenciales de WhatsApp: usan dobles
de prueba (`tests/fakes.py`) para el LLM y mockean el cliente de WhatsApp.

## 7. Cómo configurar WhatsApp (para producción real)

Ver `docs/whatsapp.md` — incluye el paso a paso completo (crear la app en Meta, obtener
credenciales, configurar el webhook). Sin esto, el sistema funciona igual para desarrollo y
pruebas vía el panel web y los tests, pero no podrá enviar/recibir mensajes de WhatsApp reales.

## 8. Cómo desplegar a producción

Ver `docs/deployment.md`. Recomendación para el MVP: Railway o Render (PostgreSQL
administrado + despliegue directo desde Git + HTTPS automático).

## 9. Cómo agregar un nuevo módulo o herramienta de IA

- Nueva entidad de negocio: agregar el modelo en `backend/app/models/`, el schema en
  `backend/app/schemas/`, la lógica en `backend/app/services/` (con auditoría), el endpoint
  REST en `backend/app/api/routes/`, y una migración con
  `alembic revision --autogenerate -m "nombre_del_cambio"`.
- Nueva herramienta de IA: ver el paso a paso en `docs/ai-tools.md` (sección "Cómo agregar
  una nueva herramienta"). Siempre debe delegar en un `service`, nunca tocar la base de datos
  directamente, y declarar su nivel de confirmación (1, 2 o 3).

## 10. Documentación completa

| Documento | Contenido |
|---|---|
| `docs/architecture.md` | Arquitectura completa, decisiones técnicas, riesgos, fases |
| `docs/database.md` | Modelo de datos, todas las tablas y relaciones |
| `docs/whatsapp.md` | Integración con WhatsApp Business Cloud API |
| `docs/ai-tools.md` | Catálogo de herramientas del agente de IA, niveles de confirmación |
| `docs/security.md` | Permisos por rol, autenticación, auditoría |
| `docs/deployment.md` | Cómo desplegar y migrar entre proveedores |

## 11. Estado del proyecto y próximos pasos

**Fase 1 (MVP) — completada en este commit:** WhatsApp (solo texto), agente de IA con tool
calling, usuarios/roles/permisos, gastos (crear/consultar/modificar/reportar), tareas
(crear/consultar/completar), base de datos PostgreSQL con migraciones, panel web mínimo,
tests automatizados.

**Pendiente (fases futuras, ver `docs/architecture.md` §9):**
- Fase 2: audio + transcripción, OCR de comprobantes, servicios técnicos, clientes, máquinas.
- Fase 3: mantenimiento preventivo + alertas, reportes avanzados (Excel/PDF), dashboard,
  Google Calendar.
- Fase 4: correo electrónico, GPS, camionetas, grúas.
- Fase 5: inteligencia empresarial (comparativas, resúmenes ejecutivos basados en datos).

No se implementó ninguna de estas para no simular integraciones que no existen todavía — ver
`docs/architecture.md` sección "Qué es real y qué es placeholder" para el detalle exacto.
