# Integración WhatsApp (Meta Cloud API)

Se usa la **WhatsApp Business Platform / Cloud API oficial de Meta**. No se usa WhatsApp Web,
Selenium, Puppeteer ni ninguna automatización no oficial (riesgo de bloqueo de cuenta).

## Requisitos previos (los provee la empresa, no el código)

1. Cuenta de **Meta Business** verificada.
2. Un número de teléfono de WhatsApp Business registrado en la **Cloud API**.
3. Una **App de Meta for Developers** con el producto "WhatsApp" habilitado.
4. Credenciales resultantes:
   - `WHATSAPP_PHONE_NUMBER_ID`
   - `WHATSAPP_BUSINESS_ACCOUNT_ID`
   - `WHATSAPP_ACCESS_TOKEN` (token permanente de sistema, no el temporal de pruebas)
   - `WHATSAPP_APP_SECRET` (para validar firma del webhook)
   - `WHATSAPP_VERIFY_TOKEN` (string propio, se define al configurar el webhook)

## Flujo de mensajes entrantes

```
Meta → POST /api/whatsapp/webhook
        │
        ├─ 1. Validar firma X-Hub-Signature-256 (HMAC con WHATSAPP_APP_SECRET)
        ├─ 2. Extraer número de teléfono del remitente + el mensaje
        ├─ 3. Buscar usuario por telefono_whatsapp
        │      no encontrado → responder "tu número no está registrado" y terminar
        ├─ 4. Según el tipo de mensaje, obtener el texto a interpretar:
        │      • texto        → se usa tal cual
        │      • audio        → se descarga y se transcribe (Whisper) — Fase 2
        │      • imagen        → se descarga y se extraen datos de comprobante (visión de
        │                        Claude), y se arma un mensaje con esos datos + el caption — Fase 2
        │      • otro tipo     → responder que ese tipo aún no se soporta y terminar
        ├─ 5. ¿Hay una PendingAction pendiente para este usuario?
        │      sí → interpretar el texto resultante como confirmación/cancelación
        │      no → continuar flujo normal
        ├─ 6. Guardar mensaje en conversation_messages (rol=user)
        ├─ 7. AgentSession.handle_message(usuario, texto)
        │        → agente LLM con tool calling, acotado a los permisos del usuario
        ├─ 8. Guardar respuesta en conversation_messages (rol=assistant)
        └─ 9. Enviar respuesta por WhatsApp (Cloud API, mensaje de texto)
```

### Verificación del webhook (`GET /api/whatsapp/webhook`)

Meta llama a este endpoint al configurar el webhook, con `hub.mode`, `hub.verify_token` y
`hub.challenge`. Se responde con `hub.challenge` solo si `hub.verify_token` coincide con
`WHATSAPP_VERIFY_TOKEN`.

### Audios (Fase 2)

`app/services/media_service.py::process_audio_message` descarga el audio
(`WhatsAppClient.download_media`) y lo transcribe con la API de Whisper de OpenAI
(`app/integrations/transcription/provider.py`) — integración real, requiere
`OPENAI_API_KEY`. El texto transcrito se guarda en `media_logs.transcript` (auditoría, sección
8 del brief) y se procesa exactamente igual que si el usuario lo hubiera escrito.

Si `OPENAI_API_KEY` no está configurada, el bot responde:

> "Por ahora no puedo transcribir audios (falta configurar el servicio de transcripción).
> ¿Puedes escribirlo como texto mientras tanto?"

en vez de fallar en silencio o inventar una transcripción.

### Fotos de comprobantes (Fase 2)

`app/services/media_service.py::process_image_message` descarga la imagen y le pide a Claude
(que sí acepta imágenes en su API — no se agregó un servicio de OCR aparte) que extraiga
proveedor, fecha, monto, moneda, número de documento, productos e impuestos, dejando en `null`
cualquier campo que no aparezca con certeza en la foto (`app/ai/receipt_extraction.py`). El
resultado se guarda en `media_logs.extracted_data` y se le presenta al agente conversacional
como contexto (junto con el texto que el usuario haya escrito como descripción de la foto) para
que complete el registro del gasto — la extracción nunca crea el gasto por sí sola, sigue
siendo el agente quien decide llamar a la tool `crear_gasto`.

Si `ANTHROPIC_API_KEY` no está configurada, o el formato de imagen no es compatible (solo
JPEG/PNG/GIF/WEBP), el bot lo indica explícitamente en vez de simular una lectura.

**Nota sobre almacenamiento (actualizado en Fase 4)**: el audio nunca se guarda de forma
permanente — se descarga, se transcribe, y se descarta. La foto de un comprobante sí se puede
guardar de forma permanente si `AWS_S3_BUCKET` (y credenciales) están configurados: en ese caso
`media_service.process_image_message` sube el archivo a S3 (`app/integrations/storage/`) y
guarda la URL en `media_logs.storage_url`, y el webhook agrega esa URL al mensaje que arma para
el agente (`"[La foto quedó guardada en <url> — usa esta URL como comprobante_url al registrar
el gasto.]"`), para que `crear_gasto` la deje registrada como comprobante. Si S3 no está
configurado, el comportamiento es el mismo que antes de Fase 4: se procesa y se descarta,
sin error — es una mejora opcional, no un requisito. Ver `docs/architecture.md` §7 y §8.

### Otros tipos de mensaje (documentos, videos, stickers, ubicación, contactos)

Todavía no soportados. El webhook responde:

> "Por ahora solo puedo procesar mensajes de texto, audios y fotos de comprobantes. Ese tipo
> de archivo todavía no lo puedo leer 🙂"

## Envío de mensajes salientes

`app/integrations/whatsapp/client.py::WhatsAppClient.send_text()` llama al endpoint
`POST https://graph.facebook.com/{version}/{phone_number_id}/messages` con
`type: text`. Es un cliente real (usa `httpx`), pero **no se puede probar de punta a punta
sin credenciales reales** — los tests unitarios lo mockean (`tests/test_webhook.py`).

### Mensajes proactivos (alertas, recordatorios) — aún no implementado

Fuera de la ventana de 24 horas desde el último mensaje del usuario, Meta exige usar
**plantillas de mensaje pre-aprobadas** (`message templates`). La Fase 3 agrega la
*detección* de mantenimiento atrasado o próximo a vencer (`buscar_mantenimiento_pendiente`,
`/api/reports/mantenimiento-pendiente`, tarjeta en el dashboard), pero **no** envía avisos
proactivos por WhatsApp todavía: eso requiere registrar una plantilla en el Business Manager
y conectar la detección a un job programado. El cliente ya deja un método
`send_template()` preparado para cuando corresponda.

## Identificación de empresa

En este MVP solo se maneja un tenant (Jacobea Forklift Chile) — no hay multiempresa. El
número de teléfono de WhatsApp Business (`WHATSAPP_PHONE_NUMBER_ID`) identifica implícitamente
a la empresa. Si en el futuro se requiere soportar múltiples empresas, la tabla `users`
necesitará una columna `company_id` y el webhook deberá resolver la empresa a partir del
`phone_number_id` que Meta incluye en el payload — la estructura del webhook ya extrae ese
campo (`app/api/routes/whatsapp.py`) para facilitar esa extensión futura.

## Cómo configurar (paso a paso, para quien no programa)

1. Crear la app en https://developers.facebook.com/apps.
2. Agregar el producto "WhatsApp".
3. En "Configuración de la API", copiar `Phone number ID` y generar un token de acceso
   permanente (token de sistema, con el permiso `whatsapp_business_messaging`).
4. Configurar el Webhook: URL pública = `https://<tu-dominio>/api/whatsapp/webhook`,
   Verify Token = el mismo valor que pondrás en `WHATSAPP_VERIFY_TOKEN`.
5. Suscribirse al campo `messages`.
6. Copiar el `App Secret` (en Configuración básica de la app) a `WHATSAPP_APP_SECRET`.
7. Completar `backend/.env` con todos los valores.
8. Registrar en la base de datos (tabla `users`, vía panel web o seed) los números de
   teléfono autorizados a usar el bot, en formato `+56...`.
