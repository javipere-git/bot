# Pendientes inmediatos (proxima sesion)

Estado: **Fase 5 (GUI) en curso.** Hechos: esqueleto + panel de Control cableado
al motor (Iniciar/Pausar/Reanudar/Detener en hilo aparte, log en vivo, contra
Tradier sandbox). GUI en `tradingbot/gui/`; lanzador `examples/correr_app.py`.

## Pendiente UX (pedido 13/07/2026)
- **Boton "Reanudar" debe estar deshabilitado mientras el bot esta corriendo activamente**
  (no pausado). Solo Pausar/Detener activos mientras corre; Reanudar se habilita cuando
  el bot esta efectivamente en pausa (por click del usuario O por auto-pausa del motor:
  tras cerrar una posicion con pause_on_fill, o al disparar el guardia/no-cierre).
  Hoy `_set_running` en main_window.py habilita Pausar+Reanudar+Detener juntos apenas
  arranca; hace falta que el motor avise sus transiciones pausa/reanuda (ej. un signal o
  callback `on_pause_change`) para que la GUI sepa el estado real y habilite el boton
  correcto.

## Ajustes del panel / flujo (pedidos del usuario, 24/06/2026)

1. **[HECHO 24/06]** Boton "Cargar archivo..." cableado: abre .txt/.csv y carga
   los simbolos al cuadro de watchlist. (Excel .xlsx queda en LISTA_DE_DESEOS:
   necesita la libreria openpyxl.)

2. **[HECHO 24/06]** Loop de watchlist opcional: check "Repetir watchlist (loop)".
   Implementado en `engine.run_watchlist` (campo `EngineConfig.loop_watchlist`).

3. **[HECHO 24/06]** Continuar tras cierre, ligado al check "Pausar al ejecutar una orden"
   (campo `EngineConfig.pause_on_fill`). Implementado en `engine.run_watchlist`:
   - Tildado: tras cerrar, se auto-pausa (reanudable; sigue con el siguiente simbolo).
   - Destildado: sigue solo.
   - Si el cierre pasa a MANUAL (guardia / 4 niveles), el bot SE DETIENE y avisa
     (posicion abierta para resolver a mano; el usuario cierra y reinicia).
   - NOTA: el flujo ahora usa `engine.run_watchlist` (reanudable). El viejo
     `run_episode` (un episodio y termina) sigue existiendo para los demos.

4. **[HECHO 24/06]** Caso manual (cierre no completado): el bot ahora se PAUSA
   (no finaliza), avisa que cierres a mano, y al Reanudar verifica que la posicion
   este cerrada antes de seguir con el siguiente simbolo.

5. **[HECHO 24/06]** Bug de carrera en el llenado: si la Orden 1 se llenaba justo
   al vencer el timeout, el bot lo tomaba como "sin llenado" (Tradier rechazaba el
   modify con "Filled"), mandaba una orden nueva y dejaba la posicion SIN trabajar.
   Ahora detecta el llenado (en el modify fallido via `_ya_lleno`, y con un
   re-chequeo al vencer cada timeout via `_entered_after_wait`) y trabaja la salida.
   Poll bajado a 0.5s. Test: `examples/demo_carrera_llenado.py`.

## Aclaraciones de comportamiento (estado actual)

- La configuracion se "congela" al apretar Iniciar. Pausar/Reanudar NO relee los
  campos. Para aplicar cambios: Detener -> modificar -> Iniciar.
  (Posible mejora futura, a evaluar: que Reanudar tome los cambios.)
- offset 100% del spread = orden cruzada (queda en el otro extremo del spread);
  en la salida equivale a tildar "cruzar".

## Despues de los ajustes (proximos pasos grandes)

- **Monitoreo** (zona central): [HECHO 24/06] Posiciones, Ordenes abiertas,
  Ejecutadas y Canceladas (conteos + ratio C/E), P/L abierto (no realizado,
  calculado con el mid vs promedio) y secciones colapsables (`CollapsibleSection`
  en `gui/widgets.py`). Todo en vivo (`MarketWorker` + `MonitorPanel` cada 4s).
  - MEJORA FUTURA (menor): P/L del DIA completo = no realizado + realizado del dia
    (este ultimo de /gainloss o del campo de /balances de Tradier).
- **Ladder** (zona derecha) - CASI COMPLETO (`gui/ladder_panel.py`):
  HECHO: escalera (bid verde / ask rojo + tamanos) centrada, FILAS COMPACTAS, ZOOM
  (paso 0.01/0.02/0.05/0.10/0.25 estilo ToS), botonera de sizes, botones marketables,
  click-para-operar (Compra/Venta), mis ordenes dibujadas en su nivel (azul) con
  click=cancelar, y marca del precio promedio (amarillo). Alimentado por quote/ordenes/
  posiciones del `MarketWorker`; opera contra un broker manual propio (sandbox).
  [HECHO] tarea 7 -> arrastrar una orden a otro nivel modifica su precio (`modify_order`,
  clase `LadderTable` que distingue click de arrastre). LADDER COMPLETO -> FASE 5 COMPLETA.
  Nota: el click en Venta manda SELL (cerrar largo); shortear manual (sell_short) = refinamiento.
  Columnas: Compra (mis ordenes) | Bid (tam) | Precio | Ask (tam) | Venta (mis ordenes).
  Tareas:
  1. Tabla del ladder (QTableWidget) con filas = niveles de precio (paso = tick),
     auto-centrada al bid/ask, con scroll y agregado de niveles al llegar al borde.
  2. Alimentarla con el quote (por ahora del polling/MarketWorker; en vivo real con
     streaming = Fase 4). Mostrar tamano en bid/ask (Level 1).
  3. Click-to-trade: click en un precio manda buy/sell limit segun el lado.
  4. Botones marketables: "Comprar al ask" / "Vender al bid".
  5. Botonera de sizes editable (10/20/50/100...).
  6. Mis ordenes dibujadas en su nivel (col Compra/Venta) con una X para cancelar.
  7. Arrastrar una orden a otro nivel = modificar su precio (`modify_order`).
  8. Marca del precio promedio de la posicion en la col Precio.
  Referencia visual/mecanica: clases `LadderTable` y `PriceMarkerDelegate` en
  `referencia_marian/trading_app.py` (es Alpaca: copiar solo el COMO se ve/comporta,
  hablando con NUESTRO motor/broker). Conviene hacerlo por partes (1-2 primero,
  despues click-to-trade, despues ordenes dibujadas + arrastre).
- **Fase 4 - streaming** [HECHO: precios en vivo]: `connectors/tradier_stream.py`
  (WebSocket market data, token de produccion SOLO lectura) + `gui/stream_worker.py`,
  alimenta el ladder en tiempo real. El sandbox no tiene streaming de cuenta, asi que
  los fills del bot se siguen detectando por polling REST (esta bien).
  PENDIENTE/mejora: usar el stream tambien para el P/L en vivo, y el Time & Sales
  (filtro "timesale", ver LISTA_DE_DESEOS).
- **Fase 6 - robustez en vivo**: [CORE HECHO] 3 strikes + capa anti-caida + freno por
  desconexion + sonido en alertas (en `engine.py` / `gui/control_panel.py`). Faltan
  [HECHO] aviso de posicion abierta al reabrir la app (`_on_positions` en main_window).
  [HECHO] rechazo de simbolo puntual (no shorteable/bloqueado/no encontrado) SALTEA el
  simbolo sin sumar strike (`_es_rechazo_de_simbolo` en engine; test en demo_robustez).
  [HECHO] estado de conexion del streaming: indicador PERMANENTE en el ENCABEZADO
  (al lado del banner): "streaming: conectado / intentando conectar... / en espera".
  Usa `esta_conectado()` del stream + ping de keepalive (asi una accion quieta NO se
  confunde con conexion caida). Se quito el indicador de "datos viejos" del ladder
  (poco util / molesto). En `main_window._actualizar_conexion` + `tradier_stream`.
  [HECHO] ordenes "fantasma" (cancelar/llenarse al mismo tiempo): toda cancelacion
  critica verifica el estado FINAL (`_cancel_and_check_fill`). Si la orden se lleno al
  cancelarla: entrada -> la toma y trabaja la salida; salida -> confirma si quedo plano
  (CLOSED) o avisa llenado parcial. Test: `examples/demo_orden_fantasma.py`.
  >>> FASE 6 (ROBUSTEZ): REFINAMIENTOS PLANEADOS COMPLETOS. Lo que resta es validarla
  con USO real en paper; el "modo LIVE" con salvaguardas es un paso aparte que requiere
  OK explicito del usuario (ver "Camino a DINERO REAL" abajo).

## Modo LIVE (dinero real) - CONSTRUIDO el 13/07/2026 a pedido del usuario
El modo LIVE existe pero esta CERRADO con un gatillo fisico: `production_account_id`
en config/credentials.ini esta VACIO y solo lo pega el usuario. Salvaguardas activas:
1. **No doble posicion** (en el motor, paper y live): si ya hay una posicion abierta
   en la cuenta (aunque sea manual), el bot NO abre otra: avisa con sonido y se pausa.
   Test: examples/demo_no_doble_posicion.py.
2. **Tope de tamano LIVE**: `[safety] live_max_shares` (hoy 25) en credentials.ini;
   si la cantidad configurada lo supera, el bot no arranca en LIVE.
3. **Doble confirmacion**: (a) al abrir, elegir LIVE exige escribir la palabra REAL;
   (b) al apretar Iniciar en LIVE, cartel resumen (simbolos/lado/cantidad) con Si/No.
4. PAPER sigue siendo el modo por defecto SIEMPRE. Banner LIVE verde + aviso en el log
   de que cada click del ladder en LIVE es una orden real.
El asistente NUNCA prueba/ejecuta LIVE contra la cuenta real: la primera corrida la
hace el usuario, con 1 accion, mirandola. Recomendacion vigente: seguir en paper hasta
validar la robustez con uso.
