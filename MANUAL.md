# Manual de funcionamiento

> Documento vivo: se va completando a medida que usamos la app y aprendemos cosas
> nuevas. Complementa a `DECISIONES.md` (por que se eligio cada cosa) y
> `PENDIENTES.md` / `LISTA_DE_DESEOS.md` (que falta).

---

## 1. Como abrir la app

- **Acceso directo "Bot Trading"** en el Escritorio (doble click, sin ventana de consola).
- O desde PowerShell: `python "C:\Users\Casa\bot trading\examples\correr_app.py"`
  (util si algo falla y hace falta ver el error).

Al abrir, elegis **broker + cuenta** (aparece un boton por cada uno configurado en
`config/credentials.ini`):
- **Tradier - PAPER** (sandbox): simulado, sin dinero real. Lo por defecto.
- **Tradier - LIVE**: dinero real. Solo aparece si cargaste `production_account_id`.
  Pide escribir la palabra **REAL** para confirmar.
- **Alpaca - PAPER**: simulado, sin dinero real. Aparece si cargaste las claves
  `paper_key_id` / `paper_secret` en la seccion `[alpaca]`.

El encabezado muestra el broker y la cuenta elegidos (naranja=PAPER, verde=LIVE).

### Correr DOS instancias a la vez (probado el 21/07/2026)
Se pueden abrir dos instancias de la app en simultaneo, operando en las dos y
recibiendo streaming en vivo en las dos. Cada una tiene su propio archivo de
registro (`registro_tradier_live.log`, `registro_alpaca_paper_datos_tradier.log`,
etc.).

Caso tipico: una instancia en Tradier LIVE y otra en Alpaca (datos de Tradier),
las dos usando el streaming de precios de Tradier. **Se comprobo en vivo que
Tradier admite VARIAS sesiones de streaming en paralelo con el mismo token**: las
dos reciben quotes sin pisarse. (Correccion: antes se creia que Tradier permitia
una sola sesion por token; NO es asi. Y aquel lag que investigamos era la PC /
el repintado del ladder, no el streaming.)

Unico limite a tener en cuenta: las dos instancias comparten el cupo de la API de
Tradier (120/min de datos, por token). El streaming casi no lo gasta, pero las
lecturas REST de precios si; con las dos operando fuerte al mismo tiempo podrias
acercarte al tope. En uso normal (una posicion por vez) no molesta.

### Diferencias entre brokers (a tener en cuenta)
- **Alpaca no distingue "vender en corto" de "vender"**: el conector lo traduce solo.
- **Lista de ordenes: solo HOY** (23/07/2026). Alpaca, a diferencia de Tradier, NO
  filtra las ordenes por dia -> el monitoreo mostraba tambien las de ayer (y su
  dashboard web hace lo mismo). Arreglado: el monitoreo pide a Alpaca solo las del dia
  de mercado de hoy (parametro `after` = 05:00 UTC, que cubre la medianoche del Este en
  verano e invierno; sirve para day trading en horario normal). "Cancelar todo" NO se
  filtra: sigue viendo TODAS las ordenes vivas por seguridad. Tradier no se toca.
- **Alpaca LIVE (dinero real)**: HABILITADO desde el 21/07/2026 (se cargaron
  `live_key_id` / `live_secret`). Hereda TODAS las salvaguardas de live: escribir REAL
  al elegir el perfil + cartel al Iniciar, tope de acciones (`[safety] live_max_shares`),
  banner verde, no-doble-posicion, y el aviso previo de corto (ver abajo). Usar la
  variante **"Alpaca LIVE - datos de Tradier"** (NBBO real), NO el feed IEX.
  Igual que con Tradier: la primera prueba real la haces vos, con 1 accion, mirando.

### OJO con la cuenta REAL de Alpaca (verificado el 21/07/2026, solo lectura)
- **NO permite ventas en CORTO** (`shorting_enabled = false`). Si configuras el bot en
  "Venta (ask-)", ahora te avisa y NO arranca (antes se hubiera comido una orden
  rechazada atras de otra). Para shortear hace falta habilitar margen en Alpaca.
- **`multiplier = 1`** = sin margen (parece cuenta CASH). En una cuenta cash el dinero
  de cada venta tarda en liquidar antes de poder reusarse, lo que choca con una
  estrategia de muchas idas y vueltas por dia. Conviene confirmarlo con Alpaca ANTES
  de fondear si vas a operar intradia seguido.
- Estado al momento de la prueba: cuenta ACTIVE, sin fondear (cash 0), sin posiciones
  ni ordenes.

### Limite de llamadas de Alpaca (200/min) y el stream de avisos
- Alpaca limita a **200 llamadas/min TODO junto** (ordenes + posiciones + cuenta),
  un solo balde. Tradier tiene baldes separados (datos 120, cuenta 300, operar 60),
  por eso el mismo bot no lo agota en Tradier pero si en Alpaca.
- El plan pago de datos (Algo Trader Plus) sube el limite de DATOS a 10.000/min, pero
  el de OPERAR sigue en 200/min. No se puede subir. (Verificado 22/07/2026.)
- Solucion cableada: el bot ya NO le pregunta a Alpaca "¿ya se lleno?" cada 0.5s.
  Alpaca nos AVISA por un stream de cuenta (trade_updates) y el bot lee el estado de
  un cache local (0 llamadas). Bajo de ~307/min a ~112/min. `connectors/
  alpaca_trade_stream.py` + el "hub" compartido en `connectors/alpaca.py`.
- SEGURIDAD: si el stream se cae, `get_order` vuelve solo a preguntar por REST (lo de
  siempre). El stream es una mejora que degrada a lo seguro; nunca opera con datos
  viejos. Solo cachea ORDENES; las posiciones se siguen leyendo por REST (para
  conservar el precio promedio y el P/L).
- Nota tecnica: el stream de paper manda el JSON en frames binarios y el de
  produccion en texto; el conector decodifica los dos. Una sola conexion por cuenta
  (compartida por todos los conectores).

### IMPORTANTE - el feed de datos de Alpaca (IEX) NO es el NBBO real
El plan gratuito de Alpaca da precios del feed **IEX** = UN solo exchange (~2-3% del
volumen). Su bid/ask **no es el NBBO consolidado**: puede estar muy corrido o faltar
un lado (ask en 0.00). Comprobado el 21/07/2026 comparando contra Tradier: MU daba
868.53 x 940.00 en IEX vs 915.76 x 916.40 real; AAPL 308.92 x 340.36 vs 324.63 x
324.90; SOFI/TTMI/RIVN sin ask. **Si el bot calcula ordenes con eso, las manda a
precios malos.** En acciones muy liquidas y con mercado abierto se acercan, pero no
es confiable para operar.

**Dos soluciones:**

1. **Pagar el feed SIP de Alpaca** (plan **Algo Trader Plus**, US$99/mes): datos
   consolidados reales (NBBO), 10.000 llamadas/min, sirve para paper y real. Es la
   opcion mas limpia: cada broker con su propia data y streaming, sin depender de
   Tradier. Al contratarlo, cambia `data_feed = iex` por `data_feed = sip` en
   `config/credentials.ini` (seccion [alpaca]) y listo: los perfiles "Alpaca - datos
   propios" pasan a usar el NBBO real y el ladder streamea bien.

2. **Perfil "Alpaca - datos de Tradier"** (gratis): opera en Alpaca pero toma los
   PRECIOS de Tradier (NBBO real, en vivo, incluido el streaming del ladder). Aparece
   si tenes las claves de Alpaca Y el token de produccion de Tradier. OJO: las dos
   instancias (Tradier + esta) comparten el cupo de datos de Tradier (120/min); en uso
   intenso simultaneo podrias acercarte al tope (ver seccion de rate limits).

**Sobre el feed IEX gratis y el streaming**: con `data_feed = iex`, el streaming de
Alpaca CONECTA pero casi no manda quotes (IEX es un solo exchange; se comprobo: 0
quotes en 30s). Es esperado y se resuelve con SIP. Ademas, el plan gratis de Alpaca
permite UNA sola conexion de streaming de datos a la vez (con Algo Trader Plus, mas).

---

## 2. El panel de Control del bot

### Watchlist
- Se carga escribiendo simbolos (separados por espacio, coma, `;` o salto de linea)
  o con el boton **"Cargar archivo..."** (.txt/.csv).

### Entrada
- **Cantidad**: acciones por orden.
- **Timeout**: segundos que espera cada orden (Orden 1 y Orden 2) antes de repreciar/pasar.
- **Lado**: Compra (bid+) entra largo / Venta (ask-) entra corto.
- **Orden 1 / Orden 2**: offset + unidad (`%` = % del spread, `$` = monto fijo). El
  offset se cuenta SIEMPRE desde el bid (compra) o el ask (venta), y es un numero
  POSITIVO que indica "que tan adentro del spread". No hace falta poner signo negativo.
  Offset 100% = orden cruzada (al otro lado del spread).
- **Spread $ min/max**: filtro; vacio = sin limite por ese lado.
- **Volumen dia min/max**: filtro por el volumen TOTAL operado en el dia (acumulado
  hasta ese momento), en acciones. Los simbolos fuera del rango se saltean (queda
  anotado en el registro). Vacio = sin limite por ese lado. Ej.: min 1000 / max 100000
  descarta lo que casi no opero y lo demasiado movido. Se puede escribir `100000` o
  `100.000`, da igual.

### Opciones
- **Pausar al ejecutar una orden**: tras CERRAR una posicion, el bot se pausa (hay
  que Reanudar para seguir con el siguiente simbolo). Destildado: sigue solo.
- **Repetir watchlist (loop)**: tildado recorre la lista una y otra vez hasta Detener;
  destildado hace una sola pasada y se detiene avisando.
- **Extended hours**: todavia NO esta cableado (usa siempre DAY).
- **Sonido al ejecutar**: sonido (distinto al de alerta) cuando se llena una orden
  (del bot o manual).

### Cierre automatico (4 niveles)
- Cada nivel: offset + unidad + timeout + **Cruzar** (ignora el offset, manda al bid/ask
  para asegurar la salida). Si un nivel tiene Cruzar tildado, los niveles siguientes se
  deshabilitan solos (una vez que cruza, cierra si o si).
- **Espera antes de cubrir**: pausa entre el llenado de la entrada y el inicio del cierre.
- **No cerrar a peor precio que el promedio (salvo cruzar)** (tildado por defecto): los
  escalones normales nunca mandan una orden por debajo del promedio (si estas largo) o
  por encima (si estas corto) — para no salir perdiendo en las tomas de ganancia. Cada
  nivel se sigue calculando con el spread del momento, pero se TOPA al promedio (piso
  redondeado al centavo para no quedar ni medio centavo peor). "Cruzar" IGNORA el tope
  (es la salida para cerrar si o si, aun con perdida). Si por el tope un escalon queda
  al mismo precio que el anterior, NO se reprecia (ahorra llamadas; util en Alpaca).
  Ejemplo: largo 10 @ 100.00, salidas 50/60/70/cruzar, mercado en 99.50x99.70 -> los
  tres primeros escalones quedan en 100.00 (no se llenan si el precio no sube), y si no
  sube, cruzar cierra al bid (99.50). Destildado = comportamiento historico (los
  escalones pueden salir por debajo del promedio).

### Guardia de movimiento en contra
- **Umbral**: en `$` o `%`. Se mide contra el **bid (si estas largo) / ask (si estas
  corto)**, tomado UNA vez segun la opcion **Referencia** (abajo). NO es tu precio de
  entrada exacto, y NO se va actualizando: es un punto de referencia fijo del trade.
- **Referencia** (desde donde se mide el umbral):
  - **Precio de calculo de la entrada** (default): el bid/ask con el que se calculo la
    orden de entrada (si hubo Orden 2, el de su recalculo). Si el precio se desploma
    JUSTO al entrar, el guardia LO VE y salta apenas arranca el cierre. El registro
    muestra "guardia mide desde X" en cada trade.
  - **Precio al iniciar el cierre**: el bid/ask leido recien al arrancar la salida
    (tras el llenado + la espera antes de cubrir, si hay). Era el comportamiento
    original; un golpe que ocurre en el instante mismo de la entrada NO lo ve
    (la referencia nace ya caida). Se cambio el default el 20/07/2026 tras perdidas
    reales por ese punto ciego.
- Ejemplo: bid 100.00, entras largo en 100.10 (referencia = 100.00). Umbral 0.15. Si
  el bid cae a 99.80 (diferencia 0.20 >= 0.15) -> se dispara. Con la referencia
  default, esto vale aunque la caida ocurra en el instante mismo de la entrada.
- **Cuando revisa**: durante TODA la salida, cada medio segundo mientras espera el
  llenado de cada nivel, Y ADEMAS justo antes de mandar/repreciar cada nivel (con la
  misma cotizacion con la que calcula el precio). Asi nunca manda la orden de un nivel
  con el mercado ya escapado: si el precio se fue en el instante del cambio de nivel,
  primero actua el guardia.
- **Accion al dispararse**:
  - (A) Pasar a manual (default): frena la salida automatica, avisa con sonido.
  - (B) Salida forzada: cruza el spread y sale al instante (tipo stop).
  - (C) Seguir: seguir con el escalonado normal (ignora el disparo).
- **Alarma continua hasta confirmar** (tildado por defecto): si el guardia se dispara
  (y paso a manual), la alarma suena REPETIDA y aparece un cartel "GUARDIA DISPARADO";
  no se apaga hasta que aprietes Aceptar. Distingue la urgencia del guardia (el precio
  se esta escapando) del paso a manual comun (los niveles no cerraron), que sigue
  avisando con un solo sonido. Destildado: todo avisa con un solo sonido, como antes.

### Cuando el bot pasa a manual
Si una posicion queda en tus manos (el guardia se disparo, o los niveles no lograron
cerrar), el bot **carga ese simbolo en el ladder solo**, listo para que lo cierres sin
tener que buscarlo ni escribirlo. Ademas suena la alerta y el bot se pausa hasta que
la posicion este cerrada. (Si ya estabas mirando ese mismo simbolo, no se toca nada.)

### Botones
- **Iniciar / Pausar / Reanudar / Detener**. Pausar frena ENTRE simbolos (no corta una
  orden en vuelo). Detener corta y hay que Iniciar de nuevo (arranca desde el primer
  simbolo de la lista).
- **REGLA DE SEGURIDAD**: el bot NUNCA abre una posicion nueva si ya hay una posicion
  abierta en la cuenta (aunque la hayas abierto vos a mano). Si detecta una, se pausa
  y avisa.
- Al reabrir la app, si detecta una posicion abierta de una sesion anterior, avisa una
  vez con sonido.

---

## 3. El Ladder

- Escribir simbolo + **Ver**. La escalera se centra sola en el bid/ask.
- **Carga automatica**: si el bot deja una posicion para cerrar a mano, el simbolo se
  carga aca solo (ver "Cuando el bot pasa a manual").
- **CONGELADA con el mouse encima** (como ThinkorSwim): mientras el cursor esta sobre
  la escalera, **los precios quedan clavados en su fila**. Es una proteccion al click:
  sin esto, si el precio se mueve justo cuando vas a clickear, la fila cambia de precio
  abajo del cursor y la orden sale a OTRO precio.
  - Lo que SI se sigue actualizando mientras esta congelada: el BID/ASK grande de
    arriba, los tamanos, tus ordenes dibujadas y la marca del promedio. Lo unico que
    se fija es QUE precio esta en QUE fila.
  - Si el precio se va FUERA de la vista, aparece un aviso abajo con el precio real
    ("CONGELADA... el precio se fue a X x Y"). Si el mercado sigue visible, no molesta
    con mensajes.
  - Al sacar el mouse, la escalera vuelve a seguir al mercado sola.
  - El boton **Centrar** funciona igual aunque el mouse este encima.
- **Re-centrado inteligente**: la escalera se vuelve a centrar SOLO cuando cambia el
  primer nivel (el precio del bid o del ask) o al cambiar el zoom. Si el NBBO no
  cambio (solo cambian los tamanos, o tus ordenes), tu scroll se respeta: podes
  explorar precios lejos del spread sin que te devuelva al centro.
- **Boton "Centrar"** (al lado del zoom): fuerza el re-centrado en el bid/ask actual.
- **Zoom** (+/-): cambia el paso de precio (0.01 / 0.02 / 0.05 / 0.10 / 0.25), util para
  acciones con spread amplio.
- **Click en Compra/Venta** (celda vacia) = manda orden limite a ese precio.
- **Tus ordenes** aparecen dibujadas en azul con "[X]"; click las cancela.
- **Arrastrar** una orden a otro nivel = modifica su precio (no cancela y remanda).
- **Marca amarilla** = tu precio promedio de la posicion.
- **"Comprar al ask" / "Vender al bid"**: ordenes marketables al instante.
- **"Cancelar todo"**: cancela TODAS las ordenes abiertas de la cuenta (util si el
  precio se mueve rapido y cuesta encontrar la orden en la escalera).
- El BID/ASK grandes arriba muestran el NBBO claramente.

**Limitacion conocida de Tradier**: Level 1 solamente. No muestra "odd lots" (ordenes
de menos de 100 acciones que quedan dentro del spread pero no marcan el NBBO). No hay
forma de verlos con la API de Tradier.

---

## 3b. Time & Sales (la cinta)

Panel a la DERECHA del ladder. Muestra las operaciones ejecutadas del simbolo que
tenes cargado en el ladder, la mas reciente arriba: **Hora, Precio, Cantidad y
Exchange**.

- **NO agrupa prints**: si salen 10 operaciones de 10 acciones, se ven las 10. Esa
  es la informacion que se lee en la cinta.
- **Color = quien fue el agresivo**, comparando contra el NBBO del momento:
  - **verde**: se dio en el ask o mas arriba (compro el agresivo),
  - **rojo**: se dio en el bid o mas abajo (vendio el agresivo),
  - **gris**: quedo dentro del spread (no se sabe). Con spreads anchos -por ejemplo
    en el overnight- es normal que casi todo salga gris.
- **Exchange**: el codigo de una letra que manda el broker (`Q` Nasdaq, `P` NYSE
  Arca, `K` Cboe EDGX, `B` Blue Ocean en el feed overnight...). Dejando el mouse
  encima aparece el nombre completo.
- **Rendimiento**: las operaciones se vuelcan a la tabla en lotes (cada 150 ms) y se
  guardan las ultimas 500. No se pierde ningun print de los que ves; lo unico que se
  limita es cuanto historial queda hacia atras.
- **De donde salen los datos**: del MISMO streaming que ya alimenta el ladder, segun
  el perfil elegido (Tradier con `timesale`, Alpaca con `trades`). No abre conexiones
  nuevas ni gasta cupo de la API.
- **Siempre sigue al ladder**: la cinta muestra el simbolo que tengas cargado en la
  escalera, lo hayas puesto vos o lo haya cargado el bot al pasar a manual. Se limpia
  sola al cambiar de simbolo.

---

## 3c. Sesion OVERNIGHT (20:00 - 04:00 ET) - solo Alpaca

Las acciones de EEUU tambien operan de noche, en **Blue Ocean ATS**, de **20:00 a
04:00 ET, de domingo a jueves**. Esa sesion NO viaja por el feed consolidado (SIP):
tiene su propio feed. Por eso:

- **Con Alpaca (plan Algo Trader Plus), la app cambia de feed sola**: al entrar en la
  sesion overnight se pasa al feed de Blue Ocean, y al terminar vuelve al normal. No
  hay que tocar nada. El ladder y el Time & Sales muestran la sesion nocturna.
- **Tradier NO tiene datos del overnight**: sus precios se quedan en el cierre de las
  20:00 ET. Es una diferencia real entre los dos brokers.
- El exchange que vas a ver en la cinta durante esa sesion es **B** (Blue Ocean).
- Los spreads del overnight son MUCHO mas anchos y hay poca liquidez: es normal ver
  la mayoria de las operaciones en gris (dentro del spread).
- Viernes a la noche y sabado no hay sesion (la semana la abre el domingo a las 20:00).
- Necesita el paquete `tzdata` (esta en requirements.txt) para saber la hora del Este
  con horario de verano. Si faltara, la app usa el feed normal, como antes.

---

## 4. Monitoreo

- **Posiciones**, **Ordenes abiertas**, **Ejecutadas**, **Canceladas** (con conteos y
  ratio C/E), todo en vivo. Secciones colapsables (flechita).
- Columna **Hora** (hh:mm:ss, hora local) en las 3 tablas de ordenes: envio (abiertas),
  ejecucion (ejecutadas), cancelacion (canceladas). Click en cualquier encabezado
  ordena por esa columna.
- **P/L del dia** (arriba, en grande): el resultado COMPLETO de la jornada, con el
  desglose debajo: **cerrado hoy** (realizado, lo que ya cerraste) **+ abierto**
  (no realizado, de lo que tenes en posicion ahora). Verde si ganas, rojo si perdes.
  Lo informa el propio broker, asi que coincide con su dashboard:
  - Tradier: campos `close_pl` (realizado del dia) + `open_pl` (abierto) de /balances.
    Verificado el 21/07/2026 contra el calculo propio de las ejecuciones del dia.
  - Alpaca: `equity - last_equity` (total del dia) y el no realizado de las posiciones.
  Se refresca cada 4 segundos junto con las posiciones.
- **Dias con MUCHAS ordenes**: las tablas de Ejecutadas/Canceladas muestran las
  ultimas 300 (dice "[muestro las ultimas 300]" al lado de los conteos); los conteos
  y el ratio siempre son sobre el TOTAL real del dia. Es para que 1500+ ordenes no
  pongan lenta la pantalla.

---

## 4b. Archivo de registro

Todo lo que aparece en el Registro de la pantalla queda tambien en un archivo, con
fecha y hora. Si la app se cierra sola, el error completo queda escrito ahi: **ese
archivo es lo primero a mirar** (y pasarselo al asistente) despues de un cierre
inesperado. Rota solo (~2 MB por archivo, guarda los 3 anteriores).

**Nombre del archivo**: `registro_<NOMBRE-DE-LA-PC>_<perfil>.log`
(ej. `registro_CASA-PC_tradier_live.log`). Lleva el nombre de la maquina para que,
si varias PCs escriben en una carpeta compartida, los registros no se pisen y se
sepa de cual vino cada uno.

**Donde se guarda**: por defecto, en la carpeta del proyecto. Se puede mandar a una
carpeta sincronizada para revisarla desde otra PC, poniendo la ruta en
`config/credentials.ini`. Con Google Drive tiene que ser una carpeta **dentro de
"Mi unidad"** (la unidad `G:` que crea Drive para escritorio): una carpeta comun del
disco `C:` no se sincroniza, y las carpetas "espejadas" de la PC suben a Drive pero
NO bajan a las otras computadoras.

```
[logs]
carpeta = C:\Users\Casa\Mi unidad\bot-logs
```

Si esa carpeta no esta disponible, el registro cae solo a la carpeta del proyecto
(nunca deja de registrar por eso).

**Version del codigo**: al abrir, la app anota en el registro la PC y la version que
esta corriendo (ej. `PC: CASA-PC | version del codigo: main c6f1c1b`). Sirve para
saber, mirando un registro de otra maquina, si tenia las ultimas correcciones o una
version vieja.

---

## 5. Indicador de conexion (encabezado)

Al lado del banner PAPER/LIVE: **"streaming: conectado / intentando conectar... / en
espera"**. Es el estado del streaming de PRECIOS en vivo (WebSocket, token de
produccion). Si dice "intentando conectar", los precios del ladder pueden estar
desactualizados; el resto de la app (monitoreo, ordenes) sigue funcionando por REST
normal.

---

## 6. Tradier — condiciones de la API (referencia)

*(Verificado contra docs.tradier.com y con pruebas reales; fecha de la ultima
verificacion: 24/06/2026 salvo que se indique otra.)*

### Cuentas y tokens
- Dos tokens separados: **sandbox** (paper) y **produccion** (real). No expiran hasta
  que se regeneran.
- Sandbox: cuenta de prueba con USD 100.000 virtuales.
- El numero de cuenta se obtiene de `GET /v1/user/profile`.

### Sandbox — limitaciones
- Datos de mercado demorados **~15 minutos**.
- **Sin streaming** de datos de mercado (`"we do not offer a delayed streaming endpoint
  for paper trading"`).
- **Sin streaming de eventos de cuenta** (`"Account activity information is
  unavailable"`) -> los fills se detectan por polling REST, no por push.
- Con el mercado CERRADO, las ordenes quedan en estado "Suspended" y **NO se pueden
  modificar** (si se pueden cancelar). El intento de modify devuelve HTTP 400
  "Order not in valid state for modifications: Suspended". El motor cae automaticamente
  a cancelar+mandar nueva en ese caso.

### Ordenes (REST)
- **Mandar**: `POST /v1/accounts/{account_id}/orders`, form-encoded (NO JSON).
  Campos: `class=equity, symbol, side, quantity, type, duration, price` (price solo
  si type=limit/stop_limit).
- **Modificar**: `PUT /v1/accounts/{account_id}/orders/{order_id}`. Permite cambiar
  `type, duration, price, stop, tag`. **NO permite cambiar la cantidad** (para eso hay
  que cancelar y mandar una nueva).
- **Cancelar**: `DELETE /v1/accounts/{account_id}/orders/{order_id}`.
- `side`: buy, sell, sell_short, buy_to_cover. `type`: market, limit, stop, stop_limit.
  `duration`: day, gtc, pre, post.
- Un HTTP 200 al mandar solo confirma "recibida", NO "ejecutada". Hay que consultar el
  estado real aparte.

### Streaming (WebSocket) — SOLO funciona con token de PRODUCCION
- **Market data** (precios): `POST /v1/markets/events/session` (con el token) crea una
  sesion (`sessionid`, vida corta). Despues conectar a
  `wss://ws.tradier.com/v1/markets/events` y mandar:
  `{"symbols": [...], "sessionid": ..., "filter": ["quote"], "linebreak": true}`.
  Filtros disponibles: `trade`, `quote`, `summary`, `timesale`, `tradex`.
  Mensaje de quote: `{"type":"quote","symbol":...,"bid":...,"bidsz":...,"ask":...,
  "asksz":...}` (ojo: los tamanos son `bidsz`/`asksz`, distinto de los nombres REST
  `bidsize`/`asksize`).
- No hace falta reconectar para cambiar de simbolos: se reenvia el mismo payload con
  la lista nueva.
- Se puede confirmar que la conexion sigue viva con un `ping` cuando no llegan datos
  (util para distinguir "conexion caida" de "accion sin movimiento").

### Rate limits (por minuto, por token)
| Categoria | Produccion | Sandbox (documentado) | Sandbox (observado en pruebas) |
|---|---|---|---|
| Lectura de cuenta (posiciones/ordenes/balances) | 120/min | 60/min | ~200/min |
| Datos de mercado | 120/min | 60/min | ~200/min |
| **Operar** (mandar+modificar+cancelar, mismo balde) | 60/min | 60/min | ~200/min |

El numero real que informa la API (headers `X-Ratelimit-*`) puede ser mas generoso que
el documentado. Igual conviene disenar pensando en el limite documentado (60/min para
operar), sobre todo pensando en produccion.

**Por que "modificar" en vez de "cancelar + mandar nueva"**: modificar el precio de una
orden gasta 1 llamada del balde de "operar"; cancelar+nueva gasta 2. Con el ciclado de
Orden1->Orden2, eso duplica cuantos simbolos se pueden recorrer por minuto. Por eso el
motor usa "modify" por defecto (configurable).

### Lista de ordenes: paginas de 1500 (IMPORTANTE, descubierto el 17/07/2026)
- `GET /accounts/{id}/orders` devuelve **como maximo 1500 ordenes por pagina**; el
  resto se pide con el parametro `page` (2, 3...). Documentado en la referencia del
  endpoint ("up to 1500 orders per market session").
- **La web y la app de escritorio de Tradier solo muestran la pagina 1**: si en el
  dia mandaste mas de 1500 ordenes, las siguientes NO aparecen en ningun lado de
  Tradier (ni en el export a Excel, que corta en 1500)... pero estan VIVAS y operan.
  Comprobado en vivo con 1542 ordenes: 3 quedaron "invisibles" y una se ejecuto sola
  al tocar su precio.
- **Nuestra app pide TODAS las paginas**, asi que muestra las 1500+ completas.
  Sintoma si te pasa en la web de Tradier: el balance cambia pero no ves por que.

### Otros
- Solo **US equities/options**, Level 1 (sin profundidad / odd lots).
- PnL del dia: Tradier no tiene "portfolio history" como Alpaca; se deriva de
  `/gainloss` o `/balances` (no implementado todavia, ver LISTA_DE_DESEOS).
- Day trading intensivo en cuentas de margen <USD 25.000 cae bajo la regla PDT.

---

## 7. Cosas aprendidas usando la app (bugs reales y su leccion)

- **Carrera de llenado en el repricio**: si la orden se llena justo cuando el bot la
  iba a modificar, Tradier rechaza el modify con "Filled". El motor lo detecta y toma
  la entrada en vez de mandar una orden nueva por error (ver `_ya_lleno` /
  `_entered_after_wait` en `engine.py`).
- **Orden fantasma**: la misma carrera pero al CANCELAR (se llena justo al cancelar).
  El motor verifica el estado final tras cada cancelacion critica
  (`_cancel_and_check_fill`).
- **Timeouts / error 504 de Tradier (21/07/2026)**: en el registro aparecian seguido
  `Read timed out` y `HTTP 504` en "Monitoreo (ordenes)" / "(posiciones)". Causa: la
  app se bajaba la lista COMPLETA de ordenes del dia (cientos, y de tarde 1500+) cada
  4 segundos, solo para mostrar tablas de consulta. En los momentos de carga esa
  llamada se pasaba de los 15s o Tradier devolvia 504 (saturacion de SU servidor).
  Arreglo FINAL (mejor que el primer intento de espaciar a 15s, que hacia lenta la
  pantalla): el endpoint de ordenes de Tradier acepta `limit` + `sort=desc`, o sea
  **las N mas recientes en una sola llamada** (verificado: 400 ordenes en 0.3s contra
  1222 en 1.7s). Ahora el monitoreo pide las 400 mas recientes cada 4s (rapido, la
  pantalla y el ladder responden al toque) y ademas hace UNA pasada COMPLETA cada 60s
  como red de seguridad, por si quedo viva una orden vieja que no entra en las
  recientes (ver el caso de las 1500). Las dos se combinan en la misma tabla.
  Las ordenes del BOT nunca fueron el problema (usa consultas por id, livianas).
  Leccion: si aparecen timeouts, mirar PRIMERO si son de "Monitoreo" (cosmetico, lo
  absorbe la robustez) o del bot.
- **Orden REEMPLAZADA (22/07/2026, encontrado operando en Alpaca con dinero real)**:
  al repreciar (Orden 1 -> Orden 2, o los niveles de salida), **Tradier MODIFICA la
  orden y conserva el id, pero Alpaca la REEMPLAZA: mata la vieja y crea una NUEVA
  con OTRO id**. El bot seguia el id viejo, cancelaba una orden ya muerta y la nueva
  quedaba HUERFANA: viva, sin control del bot, congelando el poder de compra y -lo
  mas grave- pudiendo llenarse sola y dejar una posicion sin manejar.
  Sintoma que se vio: "insufficient buying power" tras 2-3 simbolos (las huerfanas
  tenian la plata congelada) y ordenes abiertas que habia que matar con "Cancelar
  todo". Arreglado: `_orden_vigente()` en el motor: si el broker devuelve un id
  distinto, el bot pasa a seguir ESE. Para Tradier no cambia nada (mismo id).
  Leccion: no asumir que "modificar" significa lo mismo en todos los brokers.
- **El "3 strikes"** distingue un rechazo GENERAL (broker/conexion, cuenta strikes y
  puede frenar el bot) de un rechazo ESPECIFICO DEL SIMBOLO (no shorteable, bloqueado:
  solo lo saltea, no cuenta strike).
