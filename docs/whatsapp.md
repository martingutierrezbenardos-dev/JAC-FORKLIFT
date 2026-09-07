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

## Flujo de mensajes entrantes (Fase 1: solo texto)

```
Meta → POST /api/whatsapp/webhook
        │
        ├─ 1. Validar firma X-Hub-Signature-256 (HMAC con WHATSAPP_APP_SECRET)
        ├─ 2. Extraer número de teléfono del remitente + texto del mensaje
        ├─ 3. Buscar usuario por telefono_whatsapp
        │      no encontrado → responder "tu número no está registrado" y terminar
        ├─ 4. ¿Hay una PendingAction pendiente para este usuario?
        │      sí → interpretar el mensaje como confirmación/cancelación
        │      no → continuar flujo normal
        ├─ 5. Guardar mensaje en conversation_messages (rol=user)
        ├─ 6. AgentSession.handle_message(usuario, texto)
        │        → agente LLM con tool calling, acotado a los permisos del usuario
        ├─ 7. Guardar respuesta en conversation_messages (rol=assistant)
        └─ 8. Enviar respuesta por WhatsApp (Cloud API, mensaje de texto)
```

### Verificación del webhook (`GET /api/whatsapp/webhook`)

Meta llama a este endpoint al configurar el webhook, con `hub.mode`, `hub.verify_token` y
`hub.challenge`. Se responde con `hub.challenge` solo si `hub.verify_token` coincide con
`WHATSAPP_VERIFY_TOKEN`.

### Mensajes no soportados aún (Fase 1)

Si llega un mensaje de audio, imagen o documento, el webhook responde de forma clara:

> "Por ahora solo puedo procesar mensajes de texto. Pronto voy a poder escuchar audios y leer
> comprobantes 🙂"

Esto es intencional: el brief pide explícitamente no simular una integración que no existe
(OCR/transcripción llegan en Fase 2, ver `architecture.md` §9).

## Envío de mensajes salientes

`app/integrations/whatsapp/client.py::WhatsAppClient.send_text()` llama al endpoint
`POST https://graph.facebook.com/{version}/{phone_number_id}/messages` con
`type: text`. Es un cliente real (usa `httpx`), pero **no se puede probar de punta a punta
sin credenciales reales** — los tests unitarios lo mockean (`tests/test_webhook.py`).

### Mensajes proactivos (alertas, recordatorios) — fuera de Fase 1

Fuera de la ventana de 24 horas desde el último mensaje del usuario, Meta exige usar
**plantillas de mensaje pre-aprobadas** (`message templates`). Las alertas de mantenimiento
preventivo (Fase 3) y otras notificaciones proactivas deberán registrarse como plantillas en
el Business Manager antes de poder enviarse. El cliente ya deja un método
`send_template()` preparado para cuando corresponda, pero no se usa en Fase 1.

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
