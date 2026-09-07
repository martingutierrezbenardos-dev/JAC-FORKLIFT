# Despliegue

## Opción recomendada para el MVP: Railway o Render

Se recomienda **Railway** (o alternativamente Render) para el MVP porque ambos ofrecen:

- PostgreSQL administrado con un clic (backups automáticos incluidos).
- Despliegue directo desde el repo Git (build automático del backend FastAPI y del frontend
  Next.js como dos servicios separados).
- Variables de entorno gestionadas desde el panel, sin tocar el código.
- Certificado HTTPS automático (necesario para el webhook de WhatsApp, que exige HTTPS).
- Costo bajo/gratuito para el volumen de un MVP interno.

Google Cloud, AWS y Azure son más flexibles y económicos a mayor escala, pero requieren más
configuración manual (redes, IAM, certificados) que no aporta valor en esta etapa. Se
documenta la ruta de migración abajo para cuando la operación lo justifique.

## Pasos (Railway, referencia)

1. Crear un proyecto en Railway y agregar el repositorio.
2. Agregar un servicio "PostgreSQL" (Railway genera `DATABASE_URL` automáticamente).
3. Crear un servicio para `backend/` (build: `pip install -r requirements.txt`, start:
   `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT`).
4. Crear un servicio para `frontend/` (build: `npm install && npm run build`, start:
   `npm run start`).
5. Configurar variables de entorno de cada servicio según `.env.example`.
6. Una vez desplegado el backend, copiar su URL pública y configurarla como webhook en Meta
   for Developers: `https://<backend>.up.railway.app/api/whatsapp/webhook`.
7. Backups: Railway y Render ofrecen snapshots automáticos diarios de PostgreSQL en sus
   planes pagos — activar esa opción antes de manejar datos reales de la empresa.

## Separación de ambientes

- `development`: local, con `docker-compose up` (Postgres local, datos ficticios via seed).
- `staging` (opcional): mismo código, base de datos separada, credenciales de WhatsApp de
  prueba (número de test de Meta), para validar antes de producción.
- `production`: credenciales reales de WhatsApp Business, base de datos con backups
  activados, `ENVIRONMENT=production`, `DEBUG=false`.

Nunca se reutiliza la misma base de datos ni el mismo número de WhatsApp entre ambientes.

## Migración futura a Google Cloud / AWS / Azure

Cuando la operación crezca (más empresas, más volumen, necesidad de VPC/compliance):

- **Base de datos**: migrar a Cloud SQL (GCP) / RDS (AWS) / Azure Database for PostgreSQL —
  todos son PostgreSQL administrado, la migración es un `pg_dump` / `pg_restore`.
- **Backend**: contenedor Docker (`backend/Dockerfile` ya incluido) desplegable directo en
  Cloud Run (GCP), ECS/Fargate (AWS) o Container Apps (Azure).
- **Frontend**: Next.js se despliega igual de bien en Vercel, Cloud Run, o como contenedor
  estático detrás de un CDN.
- **Secretos**: mover de variables de entorno planas a un gestor de secretos (Secret Manager,
  AWS Secrets Manager, Azure Key Vault) sin cambiar el código de la aplicación (ya se lee todo
  vía `app/core/config.py`, que es el único punto de entrada de configuración).

## Docker Compose (desarrollo local)

`docker-compose.yml` en la raíz levanta:

- `db`: PostgreSQL 16.
- `backend`: FastAPI + Uvicorn, con recarga en caliente para desarrollo.
- `frontend`: Next.js en modo desarrollo.

Ver README.md para el comando exacto y las variables necesarias.

## Checklist antes de pasar a producción con datos reales

- [ ] Credenciales reales de WhatsApp Business configuradas y verificadas.
- [ ] `WHATSAPP_APP_SECRET` configurado y validación de firma probada.
- [ ] `JWT_SECRET_KEY` generado con un valor aleatorio fuerte (no el de `.env.example`).
- [ ] Backups automáticos de PostgreSQL activados.
- [ ] `ENVIRONMENT=production` y `DEBUG=false`.
- [ ] Revisar que ningún archivo `.env` esté en el repositorio (`git status` limpio).
- [ ] Usuarios reales cargados con sus roles correctos (no los datos ficticios de `seed.py`).
- [ ] Si se va a usar Google Calendar: cuenta de servicio creada, autorizada por un admin de
      Workspace para delegación de dominio completo, y `GOOGLE_SERVICE_ACCOUNT_JSON` cargado
      como secreto (no en el repositorio). Sin esto, `crear_reunion`/`consultar_calendario`
      simplemente responden que el calendario no está configurado — no bloquea el resto del
      sistema.
- [ ] Si se va a usar transcripción de audio: `OPENAI_API_KEY` configurada.
