# Lista de deseos (features para mas adelante)

> Ideas que NO construimos ahora, pero que anotamos para disenar teniendolas en
> cuenta y no olvidarlas. Agrega lo que se te ocurra; ya las afinamos cuando toque.

- **Hotkeys / atajos de teclado** para la operacion manual (entrar, salir, cancelar, etc.).
- **Tooltips de ayuda en los campos:** al dejar el mouse quieto unos segundos sobre un campo, mostrar un cartelito con una breve explicacion; desaparece al mover el mouse. (En Qt es sencillo: cada widget tiene setToolTip; falta escribir los textos de ayuda.)
- **Tablas del monitoreo - horario y orden:** [HECHO] columna Hora (hh:mm:ss local) en Ordenes abiertas (envio), Ejecutadas (ejecucion) y Canceladas (cancelacion); ordenables por cualquier columna con click en el encabezado (por defecto por hora, mas reciente arriba; orden numerico correcto en cantidades/precios).
- **P/L del dia completo (realizado + no realizado):** [HECHO 21/07/2026] lo informa el
  broker (Tradier: close_pl+open_pl de /balances; Alpaca: equity-last_equity). Se muestra
  arriba del monitoreo, en grande, con desglose "cerrado hoy | abierto". Interfaz comun:
  `Broker.get_day_pnl() -> DayPnL | None`.
- **Tablas del monitoreo - columnas customizables:** poder elegir que columnas mostrar/ocultar y su orden.
- **Encabezado - cuenta y broker:** mostrar en el banner (a la derecha de "DINERO REAL" / "SIN DINERO REAL") el numero de cuenta ENMASCARADO (****
  + ultimos 4 caracteres, ej. ****1055) y el nombre del broker (ej. "Tradier"), pensando en el futuro multi-broker.
- **Empaquetar como .exe (PyInstaller):** un ejecutable de verdad, sin depender de Python instalado (la app de Marian lo hacia asi; su codigo tiene la referencia `app_dir()` para rutas junto al .exe).
- **Ladder - boton "Cancelar todas las ordenes"**: [HECHO] boton "Cancelar todo" al lado del zoom, cancela TODAS las ordenes abiertas de la cuenta.
- **Cancelar orden desde la lista de Ordenes abiertas** (monitoreo): click derecho sobre una orden -> cancelar (o "cancelar seleccionada" / "cancelar todas"). Complementa el boton "Cancelar todo" del ladder.
- **Ladder - marcador de orden mas claro:** que la celda de la orden propia parezca mas un boton de cancelar (hoy muestra "{cant} [X]"; idealmente un boton X real con setCellWidget, cuidando de no romper el arrastre).
- **Salida parcial (scale-out):** si no se logra salir con la posicion completa, intentar con una fraccion (ej. la mitad). Ejemplo: largo 50, intento salir 50 en varios escalones; si no, pruebo con 25, y si cierran esos 25, intento de nuevo con los otros 25.
- **Filtro por volumen:** [HECHO] campos "Volumen dia" min/max en el panel de Entrada.
  Filtra por el volumen TOTAL operado en el dia (acumulado hasta ese momento, campo
  `volume` del quote de Tradier). Fuera del rango -> saltea el simbolo. Vacio = sin limite.
- **Filtro por rango de precio** (entrar solo en simbolos dentro de un rango de precio).
- **Cargar el ladder tambien cuando el bot FRENA por errores:** hoy el simbolo se carga
  solo en el ladder cuando el bot pasa a manual (guardia disparado / los niveles no
  cerraron). Falta el tercer caso: cuando frena por errores del broker (3 strikes o sin
  conexion, outcome ABORTED) y queda una posicion abierta. Seria agregar
  `self._avisar_manual(sym)` en la rama ABORTED de `_announce` (engine.py), cuidando de
  avisar solo si de verdad hay posicion abierta (ABORTED tambien puede pasar sin posicion).
- **Analisis mas fino del movimiento en contra** (velocidad de caida / momentum) en vez de solo umbral fijo, para el guardia de seguridad.
- **Importar watchlist desde archivos y portapapeles** (Excel .xlsx, CSV, .txt, y pegar desde el portapapeles). La separacion de simbolos (coma, ;, tab, espacio, salto de linea, y el `$` de `$SPY`) ya esta resuelta en el lector; falta la parte de leer archivos y portapapeles, que es de la interfaz (Fase 5).
- **Fase 6 - Robustez en vivo (ANTES de operar con dinero real):**
  - [HECHO] Contador de strikes: si una orden es rechazada/falla `max_strikes` (3) veces SEGUIDAS, el bot se detiene solo (ABORTED), deja la posicion como esta y avisa. La capa `_safe_order`/`_safe_read` del motor evita que la app se caiga ante errores del broker; si se pierde la conexion (muchas lecturas fallidas seguidas) tambien frena. Sonido del sistema al frenar/pasar a manual (beep en las alertas "***"). Todo en `engine.py` + `gui/control_panel.py`.
  - FALTA (refinamientos): un rechazo de un simbolo puntual (bloqueado / no shorteable) que SALTEE ese simbolo en vez de sumar strike; deteccion de cotizaciones "pisadas"/viejas (por antiguedad del timestamp); recuperar/avisar una posicion abierta al reabrir la app tras un cierre inesperado; ordenes "fantasma" (cancelar y llenarse al mismo tiempo); sonido con un .wav propio en vez del beep del sistema.
- **Time & Sales:** [HECHO 29/07/2026] panel a la derecha del ladder (Hora/Precio/
  Cantidad/Exchange, color segun el agresivo). Usa el streaming ya abierto del perfil
  (Tradier `timesale` / Alpaca `trades`). No agrupa prints; volcado en lotes de 150 ms
  y tope de 500 filas. Ver MANUAL.md seccion 3b.
- **Overnight (Blue Ocean ATS):** [HECHO 29/07/2026] la app elige el feed sola segun
  la sesion (20:00-04:00 ET, domingo a jueves) y reconecta el streaming al cambiar de
  sesion. Solo Alpaca (Tradier no tiene datos del overnight). Detalles tecnicos: feed
  `boats`, REST `feed=boats`, streaming `wss://stream.data.alpaca.markets/v1beta1/boats`,
  exchange `B`. Logica en `core/horarios.py`. Ver MANUAL.md seccion 3c.
- **Time & Sales (descripcion original):** panel con hora/precio/tamano de cada operacion. Se obtiene del streaming de Tradier (evento "timesale", requiere token de produccion). Sumarlo cuando montemos el streaming (Fase 4). Cuidado con el volumen de mensajes: limitar a las ultimas N filas, actualizar en lote y procesar en hilo aparte. La app de Marian ya lo tenia.
- **Aviso sonoro al pasar a manual:** ademas del cartel/notificacion, un ruido cuando el bot pasa a manual (sea por el guardia o porque no pudo cerrar con los 4 niveles). Necesita la pantalla (Fase 5).
- **Odd lots dentro del spread:** el NBBO (1er nivel) lo fijan los lotes redondos (100
  acciones, o 40 en las de mas de $250), pero dentro del spread puede haber bids/asks
  chicos (odd lots) que no marcan el NBBO.

  **QUIEN LOS TIENE (medido en vivo, 11-12/08/2026):** solo el **STREAMING de
  TASTYTRADE** (DXLink). El REST de Tastytrade, Tradier (stream y REST) y Alpaca SIP
  (stream y REST, 8.668 tamanos medidos) dan SOLO lotes redondos. Ejemplo real en AGYS,
  mismo instante: Tasty `107.87 x 7 / 108.18 x 2`, Alpaca `107.72 x 100 / 108.20 x 200`.

  **FILTRO QUE QUIERE EL USUARIO (especificado el 12/08/2026; implementar cuando se
  llegue a este punto):**

  Regla general: **los PRECIOS (entradas, salidas y guardia) se siguen calculando sobre
  el NBBO real, SIN los odd lots.** Los filtros actuales (max cambios bid/ask, max
  spread ultimos X seg, max spread en % del precio) tambien siguen midiendo sobre el
  NBBO, igual que hoy. Los odd lots se usan SOLO para el filtro nuevo.

  **El filtro nuevo:** el bot NO manda una orden si hay un odd lot posteado a un precio
  PEOR que el de esa orden (o sea, mas adentro del spread). Si el precio es EXACTAMENTE
  el mismo que el del odd lot, tambien la saltea.

  - *Entrada*: se saltea a la orden siguiente. Ejemplo: XYZ con NBBO `300 @ 100.00 x
    200 @ 101.00` y odd lots `24 @ 100.15 / 9 @ 100.48`. Orden 1 iria a 100.10, pero hay
    un odd lot de 24 en 100.15 (peor precio) -> la saltea. Orden 2 iria a 100.20, no hay
    odd lot peor -> la manda. Si SOLO hubiera una orden de entrada y quedara salteada,
    el bot no opera ese simbolo y pasa al siguiente.
  - *Salida*: misma logica. Con salidas al 60%, 40% y cruzar: la de 60% iria a 100.60 y
    hay un odd lot de 9 en 100.48 (peor precio para vender) -> saltea. La de 40% va a
    100.40, esta por debajo del odd lot -> la manda. La de cruzar SIEMPRE se manda.
  - Si TODAS las salidas quedan salteadas y hay una configurada para cruzar, va directo
    a esa. Si no hay ninguna de cruzar, pasa a MANUAL.

  **Estado tecnico:** para que el bot pueda aplicarlo, primero tiene que VER los odd
  lots. Hoy no los ve: sus precios salen del REST (`get_quote`), no del streaming. El
  observador de movimiento SI se alimenta del streaming. Habria que darle al motor
  acceso a la ultima cotizacion del streaming, igual que se hizo en el ladder.

  **Ojo de diseno:** los odd lots suelen ser de 1-2 acciones, y solo Tasty los tiene.
  Con los otros brokers el filtro tendria que quedar inactivo (comportarse como hoy).

_(Esta lista es viva: se va completando.)_
