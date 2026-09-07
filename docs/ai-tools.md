# Agente de IA y herramientas (tool calling)

## Proveedor de LLM

Se usa la **API de Anthropic (Claude)** con tool calling nativo (`tools` en la Messages API).
La integración está desacoplada en `app/ai/client.py` (interfaz `LLMClient`) para poder
cambiar de proveedor sin tocar `app/ai/agent.py` ni las tools.

Variable de entorno: `ANTHROPIC_API_KEY`. Modelo configurable vía `ANTHROPIC_MODEL`
(default `claude-sonnet-5`).

## Loop del agente (`app/ai/agent.py`)

1. Se arma la lista de mensajes: system prompt (`app/ai/prompts.py`) + últimos N mensajes de
   `conversation_messages` del usuario + el mensaje nuevo.
2. Se llama al LLM con el subconjunto de tools que el **rol del usuario** tiene permitido
   (filtrado antes de llamar al modelo — el modelo ni siquiera ve herramientas que no puede
   usar).
3. Si el modelo responde con texto → se devuelve tal cual.
4. Si el modelo pide ejecutar una tool:
   - Se valida el input contra el schema Pydantic de la tool.
   - Si `confirmation_level(tool, input, user) == 1`: se ejecuta de inmediato contra el
     servicio correspondiente, y el resultado (JSON) se agrega como `tool_result` al
     historial; se vuelve a llamar al modelo (paso 2) para que continúe o responda.
   - Si `confirmation_level >= 2`: **no se ejecuta**. Se crea un registro `PendingAction` y se
     responde al usuario con un resumen de la acción propuesta pidiendo confirmación. El loop
     termina aquí (no se sigue iterando).
5. Límite de iteraciones por mensaje: `MAX_TOOL_ITERATIONS` (default 6) para evitar loops
   costosos o infinitos.

Este flujo es la implementación concreta del principio "el LLM nunca modifica la base de
datos directamente" (brief, sección 2): el LLM solo puede *pedir* que se ejecute una función;
la decisión de ejecutarla ya, pedir confirmación, o rechazarla por permisos, es código.

## Entrada multimodal: audio e imágenes (Fase 2)

La transcripción de audio y la extracción de datos de comprobantes (fotos) NO son tools que
el LLM decida invocar — ocurren antes, en el webhook (`app/api/routes/whatsapp.py`), porque
son un paso de normalización del mensaje de entrada, no una acción sobre el negocio. El
agente conversacional solo ve el resultado como si fuera texto escrito por el usuario:

- Un audio se transcribe y el texto transcrito se le pasa a `AgentSession.handle_message`
  exactamente igual que un mensaje de texto.
- Una foto se procesa con visión de Claude y se le arma al agente un mensaje con los datos
  detectados (marcados explícitamente como "detectados automáticamente") más el texto que el
  usuario haya escrito como descripción — el agente sigue siendo quien decide, usando la tool
  `crear_gasto`, si registra el gasto y con qué datos, y puede preguntar por lo que falte
  (típicamente la categoría, que una boleta no siempre deja clara).

Ver `docs/whatsapp.md` para el detalle completo de esta parte del flujo, y
`app/ai/receipt_extraction.py` / `app/integrations/transcription/provider.py` para el código.

## Catálogo de herramientas

Definidas en `app/tools/registry.py`, implementadas en `app/tools/*_tools.py`.

| Tool | Nivel confirmación | Permiso requerido | Descripción |
|---|---|---|---|
| `buscar_usuario` | 1 | ninguno (propio contexto) | Busca datos básicos de un usuario por nombre o teléfono. |
| `crear_gasto` | 1 | `EXPENSES_CREATE_OWN` | Registra un gasto para el usuario que escribe. Nunca permite especificar `user_id` de otra persona. |
| `buscar_gastos` | 1 | `EXPENSES_READ_OWN` (auto-filtrado) o `EXPENSES_READ_ALL` | Busca gastos con filtros (fecha, categoría, proveedor). Si el usuario no tiene `READ_ALL`, se fuerza el filtro a sus propios gastos sin importar lo pedido. |
| `actualizar_gasto` | 2 | `EXPENSES_UPDATE_OWN` (propio) o `EXPENSES_UPDATE_ALL` | Modifica campos de un gasto existente. Requiere confirmación explícita del usuario. |
| `crear_tarea` | 1 si `asignado_a` es uno mismo (o vacío); 2 si se asigna a un tercero | `TASKS_CREATE_OWN` / `TASKS_ASSIGN_OTHERS` | Crea una tarea. |
| `completar_tarea` | 1 (propia) / requiere `TASKS_COMPLETE_ALL` para ajenas | `TASKS_COMPLETE_OWN` | Marca una tarea como completada. |
| `buscar_tareas` | 1 | `TASKS_READ_OWN` (auto-filtrado) o `TASKS_READ_ALL` | Lista tareas con filtros. |
| `generar_reporte` | 1 | `REPORTS_VIEW_OWN` (auto-filtrado) o `REPORTS_VIEW_ALL` | Genera un resumen de gastos, tareas o servicios (`tipo`) para un período (`periodo`: día/semana/mes, o `desde`/`hasta` explícitos), con desgloses por categoría, trabajador, proveedor, cliente, máquina o sucursal según corresponda. |
| `crear_servicio` (Fase 2) | 1 | `SERVICES_CREATE_OWN` | Crea una orden de servicio técnico para quien escribe (visita a un cliente para revisar/reparar una máquina). |
| `actualizar_servicio` (Fase 2) | 1, salvo que `estado=cerrado` (2) | `SERVICES_UPDATE_OWN` (propia) o `SERVICES_UPDATE_ALL` (ajena, requiere además `SERVICES_ASSIGN`); cerrar requiere `SERVICES_CLOSE` | Actualiza horas de salida/llegada/inicio/término, cliente, máquina, diagnóstico, trabajo realizado, repuestos, estado. Si no se indica el número de orden, usa la orden abierta más reciente de quien escribe — así el técnico puede reportar en lenguaje natural ("salí a las 8:30", "llegué donde el cliente") sin fricción. |
| `buscar_servicios` (Fase 2) | 1 | `SERVICES_READ_OWN` (auto-filtrado) o `SERVICES_READ_ALL` | Busca órdenes de servicio por estado, técnico o cliente. |
| `buscar_cliente` (Fase 2) | 1 | `CUSTOMERS_READ` | Ficha de un cliente (dirección, contacto, tipo, estado). |
| `buscar_maquina` (Fase 2) | 1 | `MACHINES_READ` | Ficha de una máquina (marca, modelo, cliente asociado, horómetro, estado, ubicación, fechas de mantenimiento). |
| `crear_mantenimiento` (Fase 3) | 1 | `MAINTENANCE_CREATE` | Registra un mantenimiento (preventivo/correctivo) de una máquina y actualiza automáticamente su horómetro y próxima fecha/horas de mantenimiento. |
| `buscar_mantenimientos` (Fase 3) | 1 | `MAINTENANCE_READ` | Historial de mantenimientos, opcionalmente filtrado por máquina. |
| `buscar_mantenimiento_pendiente` (Fase 3) | 1 | `MAINTENANCE_READ` | Lista máquinas con mantenimiento atrasado o próximo a vencer (por fecha o por horómetro). |
| `crear_reunion` (Fase 3) | 1 si no hay más participantes; 2 si hay otros participantes | `CALENDAR_USE` | Crea una reunión en Google Calendar, verificando disponibilidad de todos los asistentes antes de agendar. |
| `consultar_calendario` (Fase 3) | 1 | `CALENDAR_USE` | Consulta si quien escribe está disponible en un rango de fecha/hora. |
| `preparar_correo` (Fase 4) | 1 | `EMAIL_USE` | Prepara (crea) un borrador de correo en Gmail para uno o más destinatarios (por email o por teléfono, resuelto a su email registrado). No lo envía. |
| `enviar_correo` (Fase 4) | 2 (fijo, no depende del input) | `EMAIL_USE` | Envía un borrador ya creado con `preparar_correo`. Siempre nivel 2: nunca se envía un correo externo sin confirmación explícita (sección 14 del brief), sin excepción. |
| `buscar_correos` (Fase 4) | 1 | `EMAIL_USE` | Busca correos en la casilla de quien escribe (Gmail) por texto/remitente/asunto. |
| `buscar_vehiculo` (Fase 4) | 1 | `VEHICLES_READ` | Ficha de un vehículo de la empresa por patente (marca, modelo, año, sucursal, conductor asignado, estado). |
| `consultar_ubicacion_vehiculo` (Fase 4) | 1 | `VEHICLES_READ` | Consulta la ubicación GPS actual de un vehículo. Requiere un proveedor GPS configurado (ver `architecture.md`, sección de integraciones); sin uno, responde con un error claro en vez de simular datos. |
| `consultar_kilometraje_vehiculo` (Fase 4) | 1 | `VEHICLES_READ` | Consulta el kilometraje/horómetro reportado por el proveedor GPS del vehículo. |
| `consultar_viajes_vehiculo` (Fase 4) | 1 | `VEHICLES_READ` | Consulta el historial de viajes de un vehículo en un rango de fechas, vía el proveedor GPS. |
| `registrar_uso_grua` (Fase 4) | 1 | `CRANES_REGISTER` | Registra horas de uso de grúa contra el contrato activo de un cliente, y devuelve el saldo de horas disponibles y si el contrato está por agotarse (≥85% usado). |
| `consultar_horas_grua` (Fase 4) | 1 | `CRANES_READ` (con `cliente_nombre`) o `CRANES_MANAGE` (sin filtro, lista todos los contratos activos) | Consulta el saldo de horas de uno o todos los contratos de grúa activos. |

Cada tool declara su `input_schema` con Pydantic, que se traduce a JSON Schema para el LLM
(`model.dump_json_schema()`), así el contrato de datos es el mismo en la API REST y en la
capa de IA — una sola fuente de verdad.

Nota sobre `actualizar_servicio`: se decidió que solo **cerrar** una orden sea nivel 2. Los
reportes rutinarios de horas y diagnóstico son exactamente el flujo natural que pide la
sección 7 del brief ("Salí a las 8:30...", "Llegué donde ABC...") y exigir una confirmación en
cada uno habría reintroducido la fricción de un formulario tradicional — lo contrario de lo
que se busca. Cerrar la orden sí es una acción más definitiva (afecta reportes, facturación
futura), por eso se trata como nivel 2 y además exige el permiso `SERVICES_CLOSE`, que solo
tienen jefe de servicios técnicos, gerente general y admin del sistema.

Nota sobre `crear_reunion`: siempre requiere que quien escribe tenga un email configurado
(sin eso no hay cómo usar Google Calendar), y valida que cada participante invitado también
tenga uno — si no, rechaza la operación explicando a quién le falta, en vez de agendar solo a
medias. Antes de crear el evento, siempre verifica disponibilidad de todos los asistentes
(sección 13 del brief); si alguien tiene un conflicto, no agenda y lo informa.

## Herramientas registradas en el diseño pero fuera del catálogo del agente

La creación de contratos de grúa (`CraneContractCreate` / `POST /api/crane-contracts`) es
deliberadamente **solo REST**, no una tool de IA: abrir un contrato es una decisión
comercial/contable (define precio por hora, período, cliente) que corresponde al panel web con
el rol adecuado, no a una conversación de WhatsApp. El agente solo puede *registrar uso* contra
un contrato ya existente (`registrar_uso_grua`) y *consultar* su estado (`consultar_horas_grua`).

## Personalidad (system prompt)

`app/ai/prompts.py::SYSTEM_PROMPT` implementa la sección 23 del brief: asistente interno de
Jacobea, claro, breve, profesional, puede usar español chileno informal, nunca inventa datos
ni finge haber ejecutado una acción. Reglas explícitas en el prompt:

- Si falta un dato crítico para registrar algo, preguntar solo ese dato (no relanzar un
  formulario completo).
- Si no tiene el dato en la base de datos, decir "No tengo ese dato registrado."
- Nunca decir que hizo algo si la tool correspondiente no se ejecutó exitosamente.

El prompt es una guía de estilo y de cuándo preguntar — **no** es el mecanismo de seguridad;
los permisos y niveles de confirmación están garantizados por código (ver `security.md`).

## Trazabilidad

Toda respuesta que involucre datos agregados (`generar_reporte`) incluye en el resultado de
la tool los IDs de los registros (`expenses.id` / `tasks.id` / `service_orders.id`) usados
para el cálculo, que se guardan en `audit_logs.datos_nuevos` junto con el tool call. Esto
permite reconstruir, para cualquier cifra que la IA mencione, exactamente qué filas la
generaron (sección 31 del brief). Los reportes exportados a CSV/Excel/PDF
(`/api/reports/gastos/export`) se generan a partir de los mismos registros ya filtrados por
permisos — nunca de una consulta distinta.

## Cómo agregar una nueva herramienta

1. Definir el schema de input en `app/schemas/` (Pydantic).
2. Implementar el handler en `app/tools/<modulo>_tools.py`, que llama a un `service`
   existente (o crear uno nuevo en `app/services/`).
3. Registrar la tool en `app/tools/registry.py`: nombre, descripción (en español, clara para
   el modelo), schema, función handler, `required_permission`, y `confirmation_level` (fijo o
   una función `(input, user) -> int`).
4. Escribir un test en `tests/test_tools.py` que cubra: ejecución exitosa, rechazo por
   permisos, y (si aplica) creación de `PendingAction` en vez de ejecución directa.
