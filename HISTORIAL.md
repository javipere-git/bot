# Historial del proyecto — los porqués

> **Qué es este documento.** Un destilado de las conversaciones completas del proyecto, del **23/06/2026 al 14/08/2026** (1.666 mensajes). No repite lo que ya está en el código, en los commits o en el `MANUAL.md`: guarda **los porqués**, lo que se descartó, lo que se midió, y las preferencias del usuario que no viven en ningún archivo.
>
> **Para qué sirve.** Para que cualquier sesión futura arranque sabiendo por qué las cosas son como son, sin re-derivarlo ni proponer algo que ya se descartó.
>
> **Cómo leerlo.** La sección 1 (cómo trabajar) y la 2 (reglas de oro) son las que hay que leer siempre. El resto es consulta.

---

## 1. Cómo trabajar en este proyecto

**El usuario no es programador.** Entiende de trading, no de código. Las decisiones **técnicas** las toma el asistente (elegir, implementar, probar, corregir); las decisiones de **qué y para qué** las toma él, y se le consultan en lenguaje simple. Nada de jerga; si hay que usar un término técnico, se aclara en una frase.

**Lo que se aprendió sobre cómo trabaja, a lo largo de dos meses:**

- **Sus reportes de bugs son de altísima calidad.** Encontró la carrera de llenado, el falso positivo de "datos viejos" en acciones ilíquidas, el orden alfabético de las tablas, el agujero del guardia sin cierre automático, los odd lots que aparecían y desaparecían. **Cuando dice que algo se comporta raro, hay que ir a mirar, no a explicar.**
- **Cuando insiste, suele tener razón.** Insistió con el dato de Mariano sobre el fill rate del 99% y estaba documentado. Insistió con que las líneas de la grilla no se veían cuando yo decía que ya estaba arreglado, y tenía razón. Insistió con que lo de Tasty eran odd lots contra un comunicado de dxFeed que decía lo contrario, y tenía razón.
- **Me frenó varias veces y mejoró el diseño.** Rechazó dos parches míos en el episodio del buying power de Alpaca — y al medir lo que él pidió apareció el bug real, que era mucho peor. Rechazó el indicador de estado dentro del ladder. Propuso el tilde de Ext. hours en vez de mi versión automática, y era mejor. Propuso calcular el neto del reporte por diferencia del realizado del broker, y era mejor que mi método.
- **Antes de pedir un cambio pregunta casi siempre lo mismo**: *¿es posible? ¿es muy complicado? ¿afecta el funcionamiento del bot? ¿agrega retraso? ¿consume rate limit?* **Conviene responder esas cuatro cosas sin que las pregunte.**
- **Pide respuestas breves cuando quiere respuestas breves** ("responde breve"). Respetarlo.
- **Vigila el consumo de tokens** y avisa cuánto le queda. Si algo grande no entra completo, prefiere no arrancarlo.
- Cuando algo toca dinero real **exige certeza total**: ahí hay que releer el código, no responder de memoria.
- Le preocupa cómo lo ve el broker (si le molesta el volumen de órdenes, si lo pueden reclasificar). Es una preocupación recurrente y legítima; se responde con datos y se dice claramente qué no se puede garantizar.

**Autorizaciones**: cada pedido de permiso debe venir con una explicación breve y simple de qué se busca lograr. Nunca un pedido "a secas".

**Commits**: desde el 05/08/2026 la regla es **commitear y pushear siempre, sin preguntar**. Antes yo preguntaba al final y un cambio quedó sin subir.

**Suite de pruebas**: correr la **suite completa** antes de cada commit, no una selección. El 11/08 aparecieron tres demos rotos, dos los había roto yo cuatro días antes por correr solo unos pocos. Eran fallas de las pruebas, no de la app, pero **estaban dando falsa tranquilidad**.

---

## 2. Las reglas que no se negocian

1. **🛑 TODO en sandbox / paper. Nunca dinero real durante el desarrollo.** Si una acción *pudiera* tocar dinero real: frenar y pedir autorización con una explicación **DETALLADA y RESALTADA**. Ante la menor duda, frenar y preguntar.
2. **Yo nunca ejecuto una orden en una cuenta real.** La primera corrida real de cualquier broker la hace el usuario, con 1 acción, mirándola. Esto se cumplió con Tradier, Alpaca y Tastytrade.
3. **PAPER es el modo por defecto siempre.** Elegir LIVE exige escribir la palabra `REAL`, y apretar Iniciar en LIVE muestra un cartel resumen.
4. **Las credenciales van a `config/credentials.ini`**, que está en `.gitignore`. Nunca en el código, nunca en el chat si se puede evitar. El usuario las pega él mismo.
5. **El código de Mariano es solo referencia visual.** Está en `referencia_marian/` y en `.gitignore` porque es suyo.
6. **El bot corriendo es lo primero.** Ninguna feature accesoria puede trabarlo, agregarle latencia ni gastarle llamadas a la API.

---

## 3. La línea de tiempo

| Fecha | Qué pasó |
|---|---|
| **23/06** | Arranca el proyecto desde `CONTEXTO_proyecto.md`. Fases 0-1 (estructura + conector falso), Fase 2 (Tradier sandbox), Fase 3 completa (entrada + salida + guardia). |
| **24/06** | Validado contra Tradier real con mercado abierto: modificar funciona, ciclo entrar-salir con llenado real. PySide6 verificado en Python 3.14. |
| **25-26/06** | Llega el código de Mariano. **Fase 5 (pantalla)**: esqueleto, panel de control, monitoreo, **ladder completo**. **Fase 4 (streaming)**. **Fase 6 (robustez): 3 strikes, anti-caída, freno por desconexión.** |
| *26/06 → 13/07* | **Parate de dos semanas.** El usuario no llegó a probar la app. |
| **13/07** | Refinamientos de robustez cerrados. **Se construye el modo LIVE** a pedido suyo, cerrado con una llave física. **Primera operación real en Tradier: 2 watchlists sin problemas.** |
| **16-17/07** | El lag del ladder (throttle a 150 ms). Filtro de volumen del día. **El episodio de las 1500 órdenes.** Nace `registro_app.log`. |
| **20/07** | **Cambio de la referencia del guardia** (motivado por pérdidas reales). |
| **20-23/07** | **Alpaca cableado.** Descubrimiento de que el feed IEX no sirve. **Perfil híbrido.** El bug de las órdenes reemplazadas. Tope del precio promedio en las salidas. |
| **27-28/07** | **GitHub + Google Drive + candado de permisos.** Se monta la **segunda PC**. |
| **28-29/07** | Time & Sales. **Overnight de Blue Ocean.** Extended hours. Columnas con memoria. **Modo oscuro.** |
| **29/07** | **Giro**: Mariano comparte su app. Análisis, y decisión de contribuir un adaptador. |
| **29-31/07** | Los cuatro filtros de streaming. Ladder estilo ThinkorSwim. **La garantía DAY.** |
| **04/08** | Shorts y ETB. **Se escribe `broker/tradier.py` para la app de Mariano** (rama subida, PR sin abrir). |
| **05/08** | El crash de la app de Mariano: era `config.json`. |
| **06-07/08** | **Reporte por pasada.** Arranca Tastytrade. Análisis de por qué el ladder de Mariano es más rápido. |
| **09-11/08** | Ventana de inicio nueva. **Tastytrade completo** (sandbox + producción). **Hallazgo de los odd lots.** |
| **12-13/08** | Se descubre que el streaming de Tasty **es solo Nasdaq**. Redes de diagnóstico para los crashes. Avisos de cuenta de Tasty. Sonidos. |
| **14/08 02:27** | Última conversación, cortada por el crash de la app de escritorio. |
| **14/08** | Se destila este documento. **El ladder queda terminado**: dibujo optimista (paso 2) y órdenes verdes/rojas según el lado. |

---

## 4. Decisiones de diseño y sus porqués

### El motor

- **Arquitectura cerebro / conector / cara.** Nace desacoplada para no tener que desenredar código pegado a un broker más adelante. **Se validó tres veces**: sumar Alpaca, Tastytrade y el adaptador para la app de Mariano no obligó a tocar el motor.
- **Modificar (replace) en vez de cancelar+mandar.** Gasta 1 cupo en vez de 2. Configurable.
- **La salida siempre se calcula sobre la POSICIÓN REAL**, nunca sobre la cantidad seteada. Así un llenado parcial no rompe nada.
- **Órdenes DAY por defecto.**
- **El bot no vuelve a la watchlist hasta resolver la posición.** Si pasa a manual, se **pausa** (no finaliza) y al Reanudar verifica que la posición esté cerrada.
- **El bot NUNCA abre una posición si ya hay una** — es fijo, no depende de ningún tilde. Vale en paper y en live.
- **La config se congela al apretar Iniciar.** Para aplicar cambios: Detener → modificar → Iniciar.
- **Offset siempre positivo** = "qué tan adentro del spread arranco". El bot maneja la dirección.
- **"Cruzar" ignora el offset** y manda límite al bid/ask (nunca orden de mercado), y **apaga los niveles siguientes**.
- **Los precios de salida se recalculan con una cotización FRESCA antes de CADA nivel.** Lo único que se fija una sola vez en el cierre es la referencia del guardia.
- **Tope "no cerrar a peor precio que el promedio (salvo cruzar)".** Los escalones normales son para tomar ganancia; para salir perdiendo está cruzar. *(Salir justo al promedio es empate antes de comisiones.)*

### El guardia (la pieza más importante del bot)

- **Se revisa cada 0,5 s durante toda la salida Y justo antes de mandar cada nivel.** Lo segundo se agregó porque había una rendija real en el instante del cambio de nivel.
- **La referencia es "el precio de cálculo de la entrada"** (default). Antes se medía desde el arranque de la salida y **el guardia "nacía ciego"** si el precio se desplomaba junto con la entrada — **eso le costó dinero real al usuario**. La opción vieja sigue disponible.
- **Garantía**: con la acción en "Pasar a manual", el bot **nunca manda una orden de cierre por debajo del umbral**. Doble garantía: el precio está por encima **y** es una orden límite. Con "Salida forzada" no hay piso, y eso es a propósito: es un stop.
- **Vigila también sin cierre automático** (agujero encontrado el 29/07: el guardia vivía dentro del ciclo de niveles y si no había niveles nunca se evaluaba). En ese modo **solo avisa, nunca opera solo**.
- **La alarma suena en bucle hasta apretar Aceptar**, y después no vuelve a saltar un segundo cartel.

### La interfaz

- **Banner: PAPER naranja `#E8820C`, LIVE verde `#1e7d34`.** Elección del usuario; le marqué que la convención es rojo para LIVE y prefirió verde.
- **El indicador de conexión va en el encabezado, permanente** — no dentro del ladder (lo rechazó: molestaba y contaba mal).
- **Ladder estilo ThinkorSwim**: click en **Bid** = comprar, click en **Ask** = vender; las columnas Compra/Venta solo cancelan y mueven.
- **Con el mouse sobre la escalera, los precios quedan clavados en su fila** (idea de Mariano). El problema real era peor de lo que parecía: al moverse el precio **cambiaba qué precio estaba en cada fila**, así que se mandaban órdenes a precios equivocados. Se siguen actualizando el BID/ASK grande, los tamaños y las órdenes: se protege el click sin operar a ciegas.
- **Memoria de la interfaz**: anchos y orden de columnas de las 6 tablas, anchos de las secciones, tema, botones de cantidad y los dos tildes de avisos. **Los parámetros de trading NO se recuerdan a propósito** — que reaparezcan solos sería peligroso.
- **Los carteles y botones del ladder van SIEMPRE con el NBBO real**, nunca con el precio de un odd lot.
- **Dibujo optimista** (14/08): la orden se pinta apenas hacés clic, sin esperar al broker. **Lo no confirmado se ve distinto y no se puede clickear ni arrastrar**: gris `25 ...` enviada, ámbar `25 ->` moviéndose, gris `25 x?` cancelándose, rojo `25 !` rechazada. **Cancelar no borra la orden de la escalera a propósito** — hasta que el broker confirme sigue viva, y hacerte creer lo contrario es el error peligroso. Si el broker no contesta en 10 s, el dibujo provisorio **se borra solo** y avisa. Las confirmadas van **verdes las compras y rojas las ventas**.

---

## 5. Lo que se midió (datos duros, no documentación)

### Límites de API

| | Tradier | Alpaca | Tastytrade |
|---|---|---|---|
| Datos (precios) | **120/min** | 200/min (10.000 con Algo Trader Plus) | no publicado |
| Cuenta (posiciones/órdenes) | **300/min** | ← todo el mismo balde de **200/min** | no publicado |
| Operar | 60/min | ← idem, **el plan pago NO lo sube** | no publicado |

- **Por eso el mismo bot entra en Tradier y no en Alpaca**: en Tradier las consultas de "¿ya se llenó?" van a un carril separado de 300/min; en Alpaca todo comparte 200.
- Pasarse del límite es un **rechazo temporal (429) que se resetea cada minuto**, sin penalidad. **No existe "te reclasifican por trafico"** — eso es un mito.
- **Subir los timeouts no reduce el consumo**: el bot pregunta cada 0,5 s durante toda la espera.
- **No hay límite diario de órdenes** en ninguno.

### Calidad de los feeds

| | Prints en 30 s (SPY/F) | ¿NBBO consolidado? | ¿Odd lots? |
|---|---|---|---|
| **Tradier** streaming | 9 · 75 (**muestreado**) | Sí | No |
| **Alpaca SIP** streaming | 61 · 1.655 | Sí | **No** (8.668 tamaños medidos, ninguno fuera del múltiplo) |
| **Tastytrade** REST | — | **Sí** (9 de 12 exacto vs Alpaca) | No |
| **Tastytrade** DXLink | ~64 (**capado a ~2/s por símbolo**) | **NO — solo Nasdaq** | **SÍ** |

- **El volumen del día de Tradier SÍ es correcto** (66.811.269 vs 67.002.681 de Alpaca en SPY): lo toma de la cinta consolidada, no de sus prints. El muestreo afecta solo al TAS.

**Los filtros de streaming, medidos con mercado abierto (14/08).** Cambios de precio en 90 s, alimentando el observador real del bot con cada feed:

| | Tasty | Tradier | Alpaca SIP |
|---|---|---|---|
| AAPL (bid / ask) | 70 / 62 | 110 / 118 | **344 / 583** |
| TSLA (bid / ask) | 105 / 107 | 222 / 252 | **1.274 / 1.625** |

**Precisión importante (el usuario objetó, con razón, la primera redacción).** Los precios de Tradier son **correctos, consolidados y en tiempo real** — idénticos a Alpaca SIP símbolo por símbolo. Lo que pasa es otra cosa: **Tradier entrega los quotes con un tope de ~2,5-3 mensajes por segundo POR SÍMBOLO.** No manda cada cambio intermedio, pero el que manda es el bueno. Por eso a la vista es perfecto y coincide con Schwab.

- **No perdemos nada nosotros**: medido en crudo, recibimos 354 líneas y procesamos las 354.
- **El tope es por símbolo, no por conexión**: con 3 símbolos el total es 6,3/s y con 30 sube a 56,8/s, manteniendo ~2,5-3/s cada uno. Con watchlists grandes no se degrada.
- Tasty tiene un tope parecido (~2/s) **y además es solo Nasdaq**.

Consecuencia real, acotada: **solo los filtros que CUENTAN eventos en una ventana** se ven afectados; para decidir precios (entrada, salida, guardia) Tradier es perfecto. *(Corrección: el 12/08 predije que con Tasty "max cambios" filtraría de MÁS por el parpadeo de los odd lots. Medido, es al revés: el tope pesa mucho más.)*
- **El feed gratuito de Alpaca (IEX) no sirve para calcular órdenes**: da bid/ask disparatados (MU 868,53 × 940,00 contra 915,76 × 916,40 real) y a veces ask en 0,00. Además casi no manda quotes (0 en 30 s con mercado abierto).
- **Tradier no tiene overnight**; sus precios se congelan a las 20:00 ET. Alpaca sí, por el feed `boats` (Blue Ocean ATS, **20:00–04:00 ET, domingo a jueves**).

### Lotes redondos y odd lots

**Desde el 3 de noviembre de 2025** el lote redondo depende del precio: hasta $250 → **100**; $250,01–$1.000 → **40**; $1.000,01–$10.000 → 10; más → 1. **La asignación se revisa cada seis meses**, así que una acción que cruzó el umbral hace poco sigue con el lote viejo (AMD a $464 usa lote de 100).

> **Esto me hizo equivocar dos veces**: primero interpreté un `ask × 40` en AAPL como un odd lot cuando era un lote redondo perfecto; después una medición marcó 94 "anomalías" en AMD porque dedujo el lote del precio actual. **La forma correcta es deducir el lote de los datos** (máximo común divisor de los tamaños vistos), no del precio.

- **Desde el 1 de mayo de 2026** los SIP publican los odd lots y el **BOLO** como dato básico obligatorio. Solo el mejor de cada lado; la profundidad completa se pospuso a **2028**.
- **De los tres brokers, solo el streaming de Tastytrade los muestra** — y son **los de Nasdaq**, no todos.
- **Los odd lots están dentro del spread, así que el REST no solo redondea tamaños: esconde los mejores precios.** Medido en AGYS: streaming 107,87 × 7 / 108,18 × 2 contra REST 107,74 × 100 / 108,34 × 200 — **trece centavos peor de cada lado**.
- **IBKR tampoco los da**: su market depth los excluye explícitamente. Solo un feed crudo tipo NASDAQ TotalView-ITCH (Databento) los tiene.

### Reglas de cuenta

- **La regla PDT (los US$25.000) fue eliminada el 4 de junio de 2026.** Cierra una preocupación que se arrastró desde julio.
- **Alpaca**: no ofrece cuentas cash, todas son margin limitadas por saldo (<$2.000 → 1x sin shorting; ≥$2.000 → 2x + corto; ≥$25.000 → 4x intradiario). **Calcula el margen con el saldo del último cierre**, no con el del momento.
- **Alpaca: solo se puede shortear ETB, y las ETB tienen costo de préstamo CERO.** Las hard-to-borrow se rechazan. Si una acción pasa a HTB durante la noche, cancela las órdenes short abiertas antes de la apertura.
- **Tastytrade sí da el costo de préstamo en %** (corrección del 14/08 — antes había dicho que ningún broker lo daba). `GET /instruments/equities?symbol[]=...` devuelve, **en una sola llamada para muchos símbolos**: `borrow-rate` (medido: APLM 3,956 · KPLT 0,0914 · las ETB en 0), `lendability`, `active`, **`is-closing-only`** (bloqueada para abrir), `is-illiquid`, `is-fraud-risk`, `overnight-trading-permitted` y `pre-ipo`. Es la forma barata de saber qué símbolos están bloqueados **antes** de operarlos, sin costo por orden.
- **Tasty tiene "dry-run"** (`POST /accounts/{}/orders/dry-run`): simula la orden sin mandarla y devuelve el impacto en poder de compra, las comisiones y los avisos; si no se puede, responde **422 con el motivo en texto** (*"Trading of ZZZZQQ is not supported"*, *"Order size exceeds the limit"*). Cuesta una llamada y una vuelta de red **por orden**, así que para pre-filtrar la watchlist conviene la consulta de instrumentos; el dry-run sirve para lo que solo él responde: si **esta** orden, con **este** tamaño, entraría.
- **Criterio "non-retail" de Alpaca**: uno de sus seis criterios es **fill rate menor al 1%** (más del 99% canceladas). El usuario medía **4,39%**, y no cae en ninguno de los otros cinco. Consecuencia si lo marcaran: pierde la comisión cero y los datos pasan a tarifa profesional. **Matiz que lo perjudica**: como Alpaca reemplaza en vez de modificar, cada repricio suma una cancelación a su estadística.
- **Cancelar no cuesta plata** (el TAF de FINRA y el fee de la SEC se cobran solo sobre lo ejecutado). La SEC reporta que **el 96,8% de las órdenes del mercado se cancelan**.

### Particularidades por broker

| | Tradier | Alpaca | Tastytrade |
|---|---|---|---|
| Al modificar | **conserva el ID** | **reemplaza con ID nuevo** | **reemplaza con ID nuevo** |
| Distingue venta de venta en corto | Sí | **No** (queda corto en silencio) | Sí |
| `cancel_all` | no existe (se emula) | sí | — |
| Rechazo | **puede llegar DESPUÉS del 200 OK** (la mesa valida aparte) | inmediato | — |

- **Tradier prohíbe "short against the box"**: no se puede `sell_short` estando largo, ni cerrar un corto con un `buy` común. Por eso el mapeo largo→`sell` / plano→`sell_short` / corto→`buy_to_cover` **no es una preferencia de diseño: es lo único que acepta**.
- **Tradier pagina las órdenes de a 1500**, y su propia web solo mira la página 1.
- **Con mercado cerrado Tradier deja las órdenes "Suspended" y no permite modificarlas.**
- **Tastytrade no acepta una compra y una venta abiertas a la vez en el mismo símbolo.** En el ladder eso significa que no se puede dejar una de cada lado, como sí se puede en los otros dos.
- **Tastytrade rechaza órdenes DAY entre las 16:00 y las 16:15 NY**, y desde las 16:15 las acepta pero quedan en cola para la rueda siguiente.
- **Su sandbox usa precios reales** (la regla vieja de "límite bajo $3 se llena" ya no aplica) y **se reinicia cada 24 h**.
- **Su token de acceso dura 15 minutos**: el canal de avisos pide uno nuevo en cada latido.
- **El sandbox de Tasty a veces deja de cancelar** (17/08/2026). Contesta `HTTP 422 "the order could not be cancelled"` a cualquier `DELETE`, incluso de una compra común lejísimos del mercado — y minutos antes había cancelado esa misma clase de orden al instante. Cuando el `DELETE` sí entra, contesta `"Cancel Requested"` y la orden **vuelve a `Live`**. No es la app: es el mismo pedido, al mismo endpoint, con distinto resultado según el momento. Las que quedan son DAY, así que mueren en el cierre, y el sandbox se reinicia cada 24 h.
- **Por eso `verificar_tastytrade.py` no puede usar el mismo símbolo para el ciclo de órdenes y para el corto**: como Tasty no admite una compra y una venta abiertas en el mismo símbolo, un corto trabado envenenaba la corrida siguiente. Y su limpieza final ya no puede tumbar la corrida: antes, un cancel fallido terminaba todo en rojo **con todas las pruebas en verde**.
- **El catálogo de instrumentos del sandbox de Tasty es de mentira** (15/08/2026): lista **24.802** símbolos en 15,9 s y no marca **ninguno** — `is-closing-only` y `is-fraud-risk` vienen en `false` para los 24.802. Producción lista **13.194** en 7,5 s, con **394 bloqueadas**, 6.004 ilíquidas y 3.539 con marca de fraude. Por eso el botón de excluidas, estando en sandbox, pide el catálogo de **producción** (lectura del listado de instrumentos: no toca la cuenta ni manda órdenes) y lo avisa en el registro.

### Qué símbolos bloquea cada broker (medido el 15/08/2026)

| | Alpaca paper | Tastytrade producción | Tradier |
|---|---|---|---|
| Símbolos listados | 14.234 en **1,8 s** (una llamada) | 13.194 en **7,5 s** (14 páginas) | no lo ofrece |
| Bloqueadas para abrir | **863** (`tradable=false`) | **394** (`is-closing-only`: solo dejan cerrar) | — |
| Prestables (ETB) | 5.276 | 1.589 | — |
| Marcadas ilíquidas | no lo informa | 6.004 (45%) | — |
| Marca de fraude | no lo informa | 3.539 (27%) | — |
| Bloqueadas solo de noche | 3.526 (`overnight_halted`) | 12.638 | — |

- **`overnight_halted` (Alpaca) no bloquea la rueda normal**: es la sesión nocturna (Blue Ocean) y es **excluyente** con `overnight_tradable`.
- **Ilíquida y marca de fraude NO se usan para filtrar**: son el 45% y el 27% del mercado. Filtrar por ahí vaciaría cualquier watchlist. Se informan en el catálogo y nada más.

---

## 6. Lo que se descartó, y por qué

Para no volver a proponerlo:

- **"El ladder de Mariano anda mal porque no está en Java"** — pista falsa. Las causas reales son el feed, redibujar todo en vez de lo que cambió, la red en el hilo de la pantalla y el sondeo en vez de streaming. Eso fijó cuatro reglas de diseño del nuestro.
- **Consultar el buying power antes de cada símbolo** (Alpaca) — rechazado por el usuario: agregaba una llamada y latencia a Tradier, donde el problema no existía.
- **Saltear el símbolo cuando Alpaca devuelve error de buying power** — rechazado: "de 100 símbolos me mandaría órdenes en 30". Era esconder el síntoma; el bug real era otro.
- **Que el guardia use el precio del streaming** para bajar el consumo de la API — el usuario prefirió **pagar el SIP de Alpaca** antes que tocar el motor: *"no me gustaría tocar mucho el funcionamiento del bot en Tradier, funciona muy bien"*.
- **El indicador de estado dentro del ladder** — molestaba y contaba mal (medía desde que se cargó el símbolo, no desde el último cambio).
- **Mandar `extended_hours` automáticamente fuera de la rueda** — el usuario prefirió un tilde, para poder elegir entre ejecutar ahora o esperar la apertura. Su diseño era mejor.
- **Python 3.12 para la app de Mariano** — el crash pasaba igual. La causa era `config.json`.
- **Un filtro de volumen reciente MÍNIMO** — solo se implementó como **máximo**, porque con un feed muestreado el máximo filtra de menos (seguro) y el mínimo filtraría de más (peligroso).
- **Un ejecutable (.exe) ahora** — es para cuando la app esté estable; hoy git es mucho más ágil.
- **VPS ahora** — la app es gráfica y un VPS no tiene pantalla; lo ideal sería una versión sin interfaz, que es otro proyecto y perdería el ladder manual.
- **`openid` en el OAuth de Tasty** — no se usa, y menos permisos es más seguro.
- **Sacar el sondeo REST del ladder** — hace falta para la foto inicial, la recuperación tras un corte y como prueba de vida.

---

## 7. Los bugs que enseñaron algo

- **La carrera de llenado (25/06)** — la orden se llenaba justo al vencer el timeout, Tradier respondía "Filled" al modificar y el bot lo tomaba como "no pude modificar": mandaba una orden nueva y dejaba **la posición sin trabajar**. Arreglado en tres capas.
- **Las 1500 órdenes (17/07)** — Tradier pagina de a 1500 y su propia web solo mira la página 1. El usuario mandó 1542 y las últimas eran **invisibles pero estaban vivas**. Terminó con compras duplicadas por no verlas. **Desde entonces, la fuente de verdad es nuestra app, no la web del broker.**
- **Las órdenes huérfanas de Alpaca (22/07)** — al repreciar, Alpaca crea una orden **nueva con otro ID**; el bot cancelaba el ID viejo y **la nueva quedaba viva fuera de su control**. Congelaba el buying power, pero **el riesgo real era peor: podía llenarse sola y dejar una posición que nadie maneja**.
- **El punto ciego del guardia (20/07)** — le costó dinero real al usuario. Ver sección 4.
- **El sleep negativo (03/08)** — una carrera de milisegundos entre chequear el deadline y calcular cuánto dormir. Arreglado con doble red: el reloj **nunca duerme negativo**, y las tres cuentas se acotan en el origen.
- **El `config.json` de la app de Mariano (05/08)** — un `dock_state` corrupto hacía que Qt se cayera al restaurarlo. **Explicaba el síntoma exacto** ("funcionó las primeras veces y después nunca más"): el archivo no existía al principio.
- **La duración al modificar (31/07)** — `modify_order` mandaba siempre `day`, y Tradier rechaza cambiar la duración de una orden pre/post. **El propio código lo tenía anotado como pendiente.** El mismo bug estaba en los tres repricios del motor.
- **Los odd lots que aparecían y desaparecían (11/08)** — el sondeo REST pisaba al streaming. Mi primer arreglo usó una ventana de 5 segundos y no alcanzó: **CHCI manda un mensaje cada ~100 segundos**. El error de fondo fue decidir por tiempo: **una cotización no vence porque el mercado esté quieto**.

---

## 8. Errores míos, y qué cambió por ellos

Están acá porque las lecciones son de método, no de código:

1. **Verificar la paleta en vez de los píxeles.** Le dije al usuario tres veces que la grilla del modo oscuro estaba arreglada. **El estilo Fusion de Qt ignora la paleta** y calculaba su propio color, casi idéntico al fondo. Desde entonces **los tests dibujan la tabla en una imagen y leen el color del píxel**. La misma técnica destapó después dos bugs de la ventana de inicio.
2. **Dar por caída una corrida porque existía un archivo.** `faulthandler.log` se escribe **en cada arranque**, no solo al chocar. Varios veredictos de un rastreo entero fueron falsos positivos. Desde entonces, el archivo **arranca vacío** y se cuenta buscando "access violation".
3. **Afirmar sin medir.** Dije que Tradier permitía una sola sesión de streaming (falso, admite varias), que el mercado estaba cerrado a las 22:00 ET (Blue Ocean operaba), que Alpaca había cancelado una orden (la canceló el usuario), que la cuenta de Alpaca era cash (no ofrecen cuentas cash), y que un `ask × 40` era un odd lot (era un lote redondo).
4. **Correr una selección de tests en vez de la suite.** Rompí dos demos y no me enteré por cuatro días.
5. **Probar el caso fácil y no el que falla.** El test de los botones ETB probaba "cargar" (que no abre diálogo) y no "descargar", que era justo el que se colgaba.
6. **Arreglar la mitad visible.** En el ladder con odd lots arreglé los carteles pero no los botones: **el botón decía 108.20 y mandaba a 108.18**, peor que antes. Lo encontró el demo porque **mira a qué precio sale la orden, no solo lo que se muestra**.
7. **Aplicar una regla de más.** Le dije que no podía tocar `trading_app.py` ni siquiera localmente. La regla de Mariano es sobre lo que va en el PR, no sobre diagnosticar.
8. **Sacar algo sin preguntar.** Saqué el número de versión de la ventana de inicio porque el usuario no sabía qué era, cuando correspondía explicárselo.
9. **Medir la pantalla con la letra equivocada (15/08).** Al agregar dos botones más a la línea de las ETB, medí los anchos con la pantalla de prueba (`offscreen`), cuya letra de repuesto es **2,3 veces más ancha** que la Segoe UI de Windows. Con esa medida "los cuatro botones no entraban" y llegué a partir la línea en dos. Con la letra real piden **394 px** y el panel ya reserva **419**: entran de sobra. **Cualquier medida de tamaño de pantalla hay que tomarla en la plataforma real** (no hace falta mostrar la ventana: alcanza con no forzar `offscreen` y nunca llamar a `show()`).

**El patrón**: casi todos son *verificar lo que no es*. La contramedida que funcionó siempre fue **medir la propiedad que de verdad importa** — el píxel, no la paleta; el precio de la orden, no la etiqueta; el solapamiento de hilos, no el nombre del hilo; el lote deducido de los datos, no del precio.

---

## 9. Cosas que quedaron abiertas

**Trabajo pendiente:**
- **Foro de Medved / Schwab**: investigación a medias (el foro bloquea la lectura directa, 403).
- **Perfil "Tasty + datos de Alpaca"** — ofrecido, sin respuesta. Sería sencillo y mejoraría mucho el TAS y el filtro de volumen.
- **Los dos streamings** (NBBO de Alpaca + odd lots de Tasty) — diseñado y evaluado, sin implementar.
- **Filtro de odd lots del bot** — especificado en detalle por el usuario (ver `LISTA_DE_DESEOS.md`), sin implementar.
- **Pull Request del adaptador de Tradier** en el repo de Mariano — la rama está subida con 7 commits, **el PR sin abrir**.
- **Mostrar el fill rate en el monitoreo** con aviso al acercarse al 1%.

**Los rechazos de Tastytrade (medido el 14/08, 85 rechazos en un dia):**

| Motivo | Cuantos | Se puede evitar? |
|---|---|---|
| Poder de compra insuficiente | 40 | con tamaño por costo, no por cantidad fija |
| "set to closing only" | ~24 | **si, gratis**: `is-closing-only` en la consulta de instrumentos |
| Concentration Risk | 4 | limite propio de Tasty por exposicion |
| Halted / Do Not Trade / OTC | 10 | parcialmente, con la misma consulta |

**Sobre el poder de compra: la sospecha del usuario era correcta.** Tasty **no libera al instante** la plata congelada por una orden cancelada. La secuencia que lo prueba: a las 19:38:05 se cancela QQQP por **$4.541** y a las 19:38:08 —**tres segundos despues**— rechazan QNCX de **$670**, teniendo **$7.334** de poder de compra. Descartado que sea un bug nuestro: **0 ordenes huerfanas**, 1.930 canceladas con duracion tipica de **3 s**.
El amplificador es el **tamaño fijo**: 20 acciones sobre papeles de $200-330 son ordenes de $4.000-6.600 cada una, con una mediana de **$5.214** contra $7.334 de poder de compra. Es el mismo diagnostico que el del 22/07 con Alpaca ("10 acciones de un papel de $77 son $778 sobre $1.000"). Tasty **no expone** cuanta plata esta congelada; `equity-buying-power` ya viene neto, asi que saberlo cuesta una llamada por simbolo.

**Los prints fraccionarios de Tasty** (medido el 14/08): son **fracciones de accion de verdad**, compras por monto en dolares (0,00329 de AAPL = $1,00; 0,10266 de TSLA = $35,00). **La cinta consolidada NO los trae**: en 4.654 prints de AAPL del SIP, **cero** fraccionarios — el mas chico es 1 accion, con condicion `I` (odd lot) y exchange `D` (FINRA ADF, internalizado). Los prints "en 0" que se ven en Schwab son estos mismos, mostrados sin decimales.

**Preguntas sin responder:**
- Si Alpaca piensa exponer BOLO / odd lots (hay un hilo en su foro sin responder).
- Cuántas conexiones simultáneas de datos permite cada broker, y los límites de API de Tastytrade (no publicados).
- Si el arranque fallido de la app es por Google Drive sincronizando el log mientras está abierto (**prueba pendiente: mover el log a una carpeta local**).
- Los mails redactados para soporte de Alpaca y Tradier: no consta que se hayan enviado.

**Investigación de estrategias (proyecto aparte):**
Dos ideas evaluadas. La de **absorción en un nivel → rebote** es la mejor candidata: el stop lo define la estructura, **se puede entrar pasivo sin cruzar el spread**, y es poco sensible a la latencia. Las dos trampas: **sesgo de supervivencia** (solo se recuerdan los casos que funcionaron) y que buena parte de la "absorción" sea un algoritmo institucional que **cuando termina su cantidad deja de sostener el nivel sin avisar**.
**Lo que definiría todo el backtest es el modelo de fills, no la señal**: con un edge de 3-5 centavos, la diferencia entre suponer que uno se ejecuta en el toque o solo si el precio atraviesa es la diferencia entre +200% y -50%.
