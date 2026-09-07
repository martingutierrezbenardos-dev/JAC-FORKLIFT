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

## Catálogo de herramientas — Fase 1

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
| `generar_reporte` | 1 | `REPORTS_VIEW_OWN` (auto-filtrado) o `REPORTS_VIEW_ALL` | Genera un resumen agregado de gastos o tareas por período/categoría/usuario. |

Cada tool declara su `input_schema` con Pydantic, que se traduce a JSON Schema para el LLM
(`model.dump_json_schema()`), así el contrato de datos es el mismo en la API REST y en la
capa de IA — una sola fuente de verdad.

## Herramientas planificadas para fases futuras (documentadas, no implementadas)

Se listan explícitamente para que quede claro que existen en el diseño pero no en código
todavía (nada de esto está "simulado" en el agente):

- `crear_servicio`, `actualizar_servicio` (Fase 2, requiere `service_orders`)
- `buscar_maquina`, `crear_mantenimiento` (Fase 2/3, requiere `machines` completo +
  `maintenance_records`)
- `buscar_cliente` (Fase 2)
- `crear_reunion`, `consultar_calendario` (Fase 3, requiere integración Google Calendar real)
- `preparar_correo`, `enviar_correo` (Fase 4, `enviar_correo` siempre nivel 2: se prepara un
  borrador y se pide confirmación explícita antes de enviar, tal como pide la sección 14)
- `consultar_gps_vehiculo`, `consultar_horas_grua` (Fase 4, dependen de proveedores externos
  aún no definidos)

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
la tool los IDs de los registros (`expenses.id` / `tasks.id`) usados para el cálculo, que se
guardan en `audit_logs.datos_nuevos` junto con el tool call. Esto permite reconstruir, para
cualquier cifra que la IA mencione, exactamente qué filas la generaron (sección 31 del brief).

## Cómo agregar una nueva herramienta

1. Definir el schema de input en `app/schemas/` (Pydantic).
2. Implementar el handler en `app/tools/<modulo>_tools.py`, que llama a un `service`
   existente (o crear uno nuevo en `app/services/`).
3. Registrar la tool en `app/tools/registry.py`: nombre, descripción (en español, clara para
   el modelo), schema, función handler, `required_permission`, y `confirmation_level` (fijo o
   una función `(input, user) -> int`).
4. Escribir un test en `tests/test_tools.py` que cubra: ejecución exitosa, rechazo por
   permisos, y (si aplica) creación de `PendingAction` en vez de ejecución directa.
