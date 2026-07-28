# Decisiones del proyecto

> Registro de las decisiones importantes que vamos acordando, para no perderlas
> (el chat de la herramienta no es memoria permanente). Se actualiza a medida
> que avanzamos. El contexto general esta en `CONTEXTO_proyecto.md`.

## Arquitectura
- Tres partes separadas: **cerebro** (logica del bot) / **conector** (traductor a cada broker) / **cara** (interfaz grafica).
- El cerebro habla SIEMPRE contra una interfaz comun (`tradingbot/core/broker.py`), nunca contra Tradier directo.
- Conector de mentira (`FakeBroker`) para probar el cerebro sin tocar ningun broker.

## Seguridad con dinero (regla inviolable)
- Todo el desarrollo y las pruebas, en SANDBOX / PAPER. Nunca dinero real.
- El token de produccion, si se usa, es SOLO para ver precios en vivo (lectura). Nunca para mandar ordenes durante el desarrollo.
- Los tokens van en `config/credentials.ini` (que NO se sube). Plantilla en `config/credentials.example.ini`.

## Entrada
- Una posicion por vez, recorriendo la watchlist en orden.
- Orden 1 a (referencia + offset); si no se llena en el timeout, se trabaja la Orden 2 a otro offset; si tampoco, siguiente simbolo.
- Lado configurable: compra (bid + offset) entra largo / venta (ask - offset) entra corto.
- Offset en % del spread o en monto fijo ($/centavos).
- Filtro de spread [min, max] para decidir si se entra.
- **Duracion por defecto: DAY** (toda orden sale en DAY). Horario extendido (pre/post) seleccionable cuando se active "Extended hours".

## Re-precio de ordenes (Orden 1 -> Orden 2, y escalones de salida)
- **Por defecto: REPLACE (modificar la misma orden).** Razon: Tradier limita a 60 envios/cancelaciones por minuto entre TODOS los simbolos. Cancelar + mandar nueva gasta 2 de esos cupos; modificar gasta 1. Con replace se cicla el doble de simbolos por minuto.
- **Configurable**: se podra elegir "modificar" o "cancelar y mandar nueva" desde el bot.
- **Ojo (confirmado en la doc):** Tradier permite modificar el PRECIO de una orden viva, pero NO la cantidad. Cambiar la cantidad (ej. la "salida parcial"/scale-out) obliga a cancelar y mandar una nueva.
- **Hallazgo (mercado cerrado, 23/06/2026):** con el mercado cerrado Tradier deja las ordenes en estado "Suspended" y NO permite modificarlas (cancelarlas si). Por eso el motor, si una modificacion falla, cae automaticamente a cancelar+nueva. Validar "modificar" contra Tradier real requiere MERCADO ABIERTO. -> VALIDADO el 24/06/2026 con mercado abierto: el modify funciona (8/8 en la watchlist de prueba), recorriendo mandar -> modificar -> cancelar. Tambien VALIDADO el CICLO COMPLETO con llenado real en GE (entrada que cruza -> llenado detectado -> salida cruzando -> cuenta plana).

## Salida (cierre automatico)
- Hasta 4 escalones configurables (cada uno: activable, offset, unidad %/$, timeout, y opcion "cruzar" el spread para asegurar la salida).
- Los escalones se calculan sobre el precio VIVO del momento (acompanan al mercado).
- **La cantidad de salida sale SIEMPRE de la posicion real, no de la cantidad seteada** (a prueba de llenados parciales).
- Espera configurable entre el llenado y el inicio del cierre.

## Guardia de movimiento en contra (freno de seguridad)
- Se mide el movimiento en contra contra el **bid (si estamos largos) / ask (si estamos cortos)**.
- Umbral configurable en centavos o %.
- Solo se dispara si el movimiento es sustancial (cruza el umbral); movimientos chicos no lo activan.
- Al dispararse, accion configurable por trade:
  - **(A) Pasar a manual** *(opcion por defecto)*: frena la salida automatica y avisa (sonido + cartel); el control queda en el ladder.
  - **(B) Salida forzada**: cruza el spread y sale al instante (tipo stop loss).
  - **(C) Seguir** con el escalonado normal.

## Limitaciones del sandbox (confirmadas con Tradier, 23/06/2026)
- Datos de mercado **demorados 15 min** y **sin streaming** (lo dice el propio panel de Tradier y la doc). Para precios en vivo (ladder) hace falta el token de produccion, SOLO lectura.
- **"Account activity information is unavailable"**: en paper NO hay stream de eventos de cuenta. -> En sandbox los llenados se detectan **consultando el estado de las ordenes por REST (polling)**, no por push. Eso usa el balde "standard" (60/min en sandbox), aparte del balde de operar (60/min).
- Token de sandbox: no caduca hasta regenerarlo. Cuenta paper con USD 100.000 virtuales.

## Rate limits (re-verificados el 23/06/2026 en docs.tradier.com/docs/rate-limiting)
- Standard (leer cuenta, ordenes, watchlists; NO incluye mandar): 120/min produccion, 60/min sandbox.
- Datos de mercado: 120/min produccion, 60/min sandbox.
- **Operar (mandar + modificar + cancelar, mismo balde): 60/min en produccion Y en sandbox.**
- **Observado EN VIVO (sandbox, 23/06/2026):** la API reporta `Allowed=200` tanto en lectura como al mandar/cancelar ordenes -> mas holgado que el 60 documentado. El 60 podria aplicar solo en produccion (que igual usaremos solo para leer precios). La preferencia "modificar por defecto" se mantiene igual (es lo mas eficiente y gratis de mantener).

## Consideraciones de diseno del ladder / GUI (para la Fase 5)
Marian (su app en Alpaca) renegaba con el ladder; sospechaba del lenguaje (Python vs Java de ThinkorSwim), pero el lenguaje casi seguro NO es la causa. Causas reales tipicas a evitar:
- **Feed de datos:** el feed gratuito de Alpaca (IEX) es parcial; se ve "raro". Nosotros usaremos el streaming en tiempo real de Tradier (token de produccion, SOLO lectura). Recordar: Tradier es Level 1 (tamano en bid/ask, sin profundidad).
- **Fluidez:** actualizar SOLO lo que cambia en el ladder, no redibujar todo en cada tick.
- **Threading:** la red/broker en un hilo APARTE del hilo de la interfaz, para que la ventana no se congele. (PySide6/Qt es C++ por debajo, performante; el lenguaje no es el cuello de botella si se disena bien.)
- **Streaming, no polling**, para alimentar el ladder.

## Stack
- Python. GUI con PySide6 (Qt). Tradier por REST (`requests`) + streaming (`websocket-client`).
