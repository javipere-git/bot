# Contexto del proyecto — Bot de trading + Ladder (Tradier)

> **Qué es este documento.** Es el *briefing* del proyecto: explica **qué** queremos construir, **por qué**, y **cómo** quiero trabajar. **No es una lista de tareas ni una orden de ejecutar nada.** Es solo contexto.
>
> **Primer paso esperado en Claude Code:** leer este documento completo, hacerme las preguntas que hagan falta, y **proponer juntos un resumen y un plan por fases** antes de tocar una sola línea de código o ejecutar cualquier cosa.

---

## 1. Quién soy y cómo necesito que trabajes

- **No soy programador.** Entiendo de trading, no de código. Hay decisiones técnicas que directamente no sé responder (ejemplo real de una pregunta que no entendí: *"¿arrancamos por la interfaz común o por un script de conexión?"*). Ese tipo de disyuntivas técnicas **las tenés que resolver vos**, no yo.
- Ante una decisión técnica: **elegí la opción razonable, implementala, probá el resultado, corregí si hace falta, y repetí hasta que funcione.** No me pidas que decida cuestiones técnicas que no puedo evaluar.
- Lo que sí decido yo es el **qué** y el **para qué** (la funcionalidad, el comportamiento, las prioridades). Eso consultámelo en lenguaje simple.
- **Explicá en lenguaje no técnico** lo que vas haciendo y por qué. Evitá la jerga; si tenés que usar un término técnico, aclaralo en una frase.

### Autorizaciones
- Cada vez que me pidas autorización para una acción, el pedido **debe venir con una explicación breve y en lenguaje simple** de qué buscás lograr con esa acción. Nunca un pedido "a secas".

### ⚠️ SEGURIDAD CON DINERO REAL — REGLA INVIOLABLE ⚠️
- **TODO el desarrollo y TODAS las pruebas se hacen en SANDBOX / PAPER (dinero simulado). NUNCA con dinero real.**
- **Está prohibido ejecutar cualquier acción que toque mi cuenta real / dinero real** durante el desarrollo. Esto incluye, pero no se limita a: **enviar órdenes reales, cerrar posiciones reales, mover fondos, modificar la cuenta.**
- Si en algún momento una acción *pudiera* involucrar dinero real, **NO la ejecutes por tu cuenta**. Pedime autorización con una explicación **DETALLADA y RESALTADA** (MAYÚSCULAS, **negritas**) que deje clarísimo que **INVOLUCRA DINERO REAL**, qué haría exactamente, y qué consecuencia tendría. Recién con mi confirmación explícita se avanza.
- Ante la menor duda de si algo toca dinero real: **frená y preguntá.**

---

## 2. Objetivo final

Construir una **aplicación de escritorio de trading** parecida a una que un amigo (Marian) hizo con Claude para **Alpaca**, pero:

1. **Para Tradier** como broker (en lugar de Alpaca).
2. **Diseñada desde el día uno para ser "multi-broker"**: con una capa de adaptador ("conector") que aísle todo lo específico del broker, de modo que en el futuro se pueda sumar Alpaca, IBKR, etc., **escribiendo un adaptador nuevo, sin reescribir la app**.

### Filosofía de arquitectura (importante)
- Separar la app en **"cerebro"** y **"cara"**:
  - **Cerebro** = la lógica de negocio: la máquina de estados del bot + la comunicación con el broker. **Esto se construye nuevo y limpio**, hablando siempre contra una **interfaz común** (no contra Tradier directo).
  - **Conector** = la implementación concreta de esa interfaz para Tradier (traduce los pedidos genéricos —comprar, cancelar, posiciones, stream de quotes, stream de fills— a las llamadas reales de Tradier). Sumar otro broker = otro conector.
  - **Cara (GUI)** = la interfaz visual. El código de Marian **podría llegar más adelante como referencia visual** para no rehacer toda la GUI desde cero. Aclaración: si llega, es **solo referencia**, NO para fusionar (su código está cableado a Alpaca por todos lados; heredar eso traería el problema que justamente queremos evitar).
- La razón de nacer desacoplado: evitar el trabajo de "desenredar" un código ya pegado a un broker. Mejor hacerlo bien de entrada.
- Beneficio extra de la abstracción: permite tener un **"conector falso/simulado"** para probar el cerebro sin tocar ningún broker.

### Referencia visual
La app de Marian (de la que tengo capturas) es el **objetivo visual**: una ventana de escritorio con tres zonas (control del bot a la izquierda, paneles de monitoreo en el centro, ladder a la derecha). Más abajo se detalla la funcionalidad.

---

## 3. La estrategia que automatiza la app

- El usuario carga una **lista de símbolos** (watchlist).
- El bot recorre la lista **de a un símbolo a la vez, en forma secuencial** (NO opera todos a la vez; una posición por vez).
- **Por cada símbolo:**
  1. Envía una **Orden 1** (límite) a un precio = referencia + offset.
  2. Si **no se ejecuta** dentro de un *timeout* configurable → **la cancela** y envía una **Orden 2** a otro offset.
  3. Si la Orden 2 **tampoco se ejecuta** dentro del timeout → la cancela y **pasa al siguiente símbolo**.
  4. Si **alguna se ejecuta** (fill) → ver "Cierre" abajo.
- **Lado configurable:**
  - **Compra (bid +):** entra largo a `bid + offset`.
  - **Venta (ask −):** entra corto a `ask − offset`. *(El corto requiere cuenta de margen y papel prestable; en paper suele entrar igual.)*
- **Offset configurable** en dos unidades, a elección por orden: **% del spread** o **monto fijo en $/centavos** (ej. `bid + $0.01`). Si el offset es 0%/$0 → queda al bid (o ask) puro.
- **Cierre automático escalonado** (esto cubre la idea de "ir bajando la orden de salida hasta el bid"):
  - Al ejecutarse una entrada, el bot **se pausa solo** y trabaja la salida con **hasta 4 niveles configurables** (cada nivel: activable con un check, su offset, su unidad %/$, su timeout).
  - La salida es del **lado contrario** a la entrada: si entró largo, vende cerca del ask y va bajando; si entró corto, compra cerca del bid y va subiendo.
  - Cada nivel puede marcarse **"cruzar" (al bid/ask)**: cruza el spread para **asegurar la salida** (al bid si está largo, al ask si está corto). Cuando "cruzar" está activo, el offset de ese nivel se ignora.
  - Secuencia: coloca nivel 1, espera su timeout; si no se llena, lo cancela y pasa al siguiente; si ninguno entra, deja la posición abierta y avisa.
  - Hay una **espera configurable** entre el momento del fill y el inicio del cierre.
- **Filtro de spread para la entrada:** solo enviar la orden de entrada si el spread (ask − bid, en $) cae dentro de un rango `[mín, máx]`. Cualquiera de los dos campos puede quedar vacío = sin límite por ese lado (ej.: mín 0.03 y máx vacío → solo símbolos con spread ≥ 0.03).

---

## 4. Funcionalidad de la app (alcance objetivo)

Tomado del set de features que Marian fue construyendo. No hace falta lograr todo de una; servirá para el plan por fases.

**Control del bot**
- Watchlist (cargar desde un archivo o pegar; separado por espacio/coma/línea).
- Cantidad fija de acciones por orden.
- Timeout de cada orden.
- Selector de **Lado** (Compra bid+ / Venta ask−).
- Configuración visible de **Orden 1** y **Orden 2** (offset + unidad %/$).
- Filtro de spread (mín/máx).
- Checks: "Pausar al ejecutar una orden", "Extended hours", "Sonido al ejecutar".
- Sección "Cierre automático (4 niveles)" con su interruptor maestro y la grilla de niveles + "Espera antes de cubrir".
- Botones: **Iniciar / Pausar / Reanudar / Detener** (Pausar conserva el lugar; Detener corta y reinicia desde el principio).
- **Registro** (log) de lo que va pasando, visible en la ventana.

**Paneles de monitoreo (estilo Activity de Schwab/ToS)**
- **Posiciones:** toggle "Solo abiertas / Todas del día", con **PnL del día** siempre visible (verde/rojo). Click en una posición la lleva al ladder.
- **Órdenes abiertas:** con cancelar seleccionada / cancelar todas.
- **Ejecutadas** y **Canceladas:** con **conteos** y **ratio canceladas/ejecutadas** + % del total (útil para medir cuán selectivo es el llenado).
- Secciones **colapsables** (flechita estilo ToS).

**Ladder (DOM) — Level 1**
- Columnas: Compra (mis órdenes) · Bid (tamaño) · Precio · Ask (tamaño) · Venta (mis órdenes).
- La escalera abarca siempre del bid al ask + margen, se auto-recentra, y permite **scroll** para ver muchos más niveles (se agregan al llegar al borde).
- **Click-to-trade:** click a un precio manda buy/sell limit según el lado.
- **Botones marketables:** "Comprar al ask" / "Vender al bid" (son límite, pero al precio del otro lado del spread).
- **Botonera de sizes** editable por el usuario (ej. 10, 50, 100…).
- Mis **órdenes dibujadas en su nivel** con una ✕ para cancelar desde ahí; **arrastrar** la orden a otro nivel **modifica su precio**; cancelar/mover se refleja al instante.
- Marca del **precio promedio** de la posición en la columna Precio (flechitas ▸ ◂).
- Filas compactas, columnas redimensionables.

**General**
- Modo **Paper / Live** elegido al abrir, con **cartel bien visible** (verde PAPER / rojo LIVE). *(Recordatorio: durante el desarrollo, siempre Paper. Ver regla de dinero real.)*
- **Persistencia**: auto-guardado del último estado + presets con nombre + tamaño/posición de ventana + anchos de columnas.
- Módulos redimensionables (divisores arrastrables) y panel de control que se puede angostar.
- Cierre prolijo de la app (sin que quede colgada) y log a archivo para diagnóstico.

---

## 5. Stack técnico (lo que ya sabemos que sirve)

- **Lenguaje:** Python.
- **GUI:** **PySide6 (Qt)** — es lo que usó Marian y es lo adecuado para un ladder que se actualiza en vivo y responde a clicks.
- **Conexión a Tradier:** **`requests`** para REST + **`websocket-client`** para streaming. (Tradier **no** tiene un SDK oficial tan pulido como el `alpaca-py` de Alpaca; existe alguna librería comunitaria, pero armar la capa con `requests`/`websocket-client` da más control y transparencia.)
- **Arquitectura:** separación cerebro / conector descrita en la sección 2.

---

## 6. Tradier — información de referencia verificada

*(Datos confirmados contra la documentación de Tradier. Se incluyen para no partir de memoria desactualizada. No son instrucciones de ejecución, son referencia.)*

**Autenticación**
- Un único **Bearer token** en el header `Authorization`. Para usuarios individuales, el token se genera en `web.tradier.com/user/api` y **no expira**.
- Hay **dos tokens distintos**: uno de **producción** y uno de **sandbox**. Nunca van hardcodeados en el código; van en un archivo aparte / variable de entorno.

**Sandbox (paper)**
- Prefijo `sandbox.tradier.com/v1`. Simula ejecuciones con dinero de mentira.
- **Limitación clave:** el sandbox **no tiene streaming de market data** y sus datos llevan ~15 min de retraso. → Para ver el ladder en vivo se necesita el **token de producción** (pero el streaming de quotes es **solo lectura**, no ejecuta nada: no toca dinero).

**Órdenes (REST)**
- **Colocar:** `POST /v1/accounts/{account_id}/orders`, **form-encoded** (no JSON). Campos típicos: `class=equity`, `symbol`, `side`, `quantity`, `type=limit`, `duration=day`, `price`.
- **Modificar:** `PUT /v1/accounts/{account_id}/orders/{order_id}` (sirve para el arrastre en el ladder).
- **Cancelar:** `DELETE /v1/accounts/{account_id}/orders/{order_id}`.
- Hace falta el **`account_id`** en la URL (se obtiene de `GET /v1/user/profile`).
- Un `200 OK` al enviar significa "recibida", **no** "ejecutada": el estado se consulta aparte (idealmente por el stream de cuenta).
- Existe `preview=true` para previsualizar; Tradier lo recomienda, pero aclara que en trading algorítmico (donde importa la velocidad) algunos lo saltean (cuesta una call extra por orden).

**Lado y sesiones**
- **Extended hours:** no es un flag; se usa `duration=pre` o `duration=post`.
- **Corto:** `side=sell_short` / `buy_to_cover` (requiere cuenta de margen).

**Streaming (WebSocket)**
- Dos streams: **market data** (quotes del ladder) y **cuenta** (avisos de fills/cambios de orden).
- Mecánica: primero un `POST` crea una **sesión** de vida corta (un `sessionid`), después se conecta al WebSocket y se le manda ese id + símbolos + filtro (`quote` para datos).
  - Market data: `wss://ws.tradier.com/v1/markets/events`.
  - Cuenta: `wss://ws.tradier.com/v1/accounts/events`.
- **Solo una sesión a la vez** de cada tipo. **Reconexión obligatoria** (la conexión se cae y hay que reconectar solo).
- Conviene usar **WebSocket para quotes y fills**, no polling REST (el polling consume rate limit; el streaming no).

**Rate limits (por minuto, por token; headers en cada respuesta)**
- **Datos de cuenta** (posiciones, órdenes, balances — *no* incluye mandar órdenes): 120/min producción, 60/min sandbox.
- **Datos de mercado** (`/markets`): 120/min producción, 60/min sandbox.
- **Scope "trade"** (mandar, modificar y cancelar órdenes — todo junto): **60/min en producción y en sandbox**.
- **Cuello de botella para el ciclado:** mandar y cancelar comparten el balde de 60/min. Un símbolo que no se llena consume ~4 calls (orden 1 + cancelar + orden 2 + cancelar) → techo de **~15 símbolos/min** si nada se ejecuta. Es el límite real del recorrido, más que el timeout. (Mitigaciones: quotes/fills por WebSocket; eventualmente una sola orden por símbolo en vez de dos.)

**Otros**
- **Level 1 únicamente** (igual que Alpaca): el ladder mostrará tamaño en el bid/ask, no profundidad de Level 2.
- Solo **US equities/options**.
- **PnL del día:** Tradier no tiene un "portfolio history" como Alpaca; se deriva de `/gainloss` o `/balances`.
- *(Operativo, para más adelante / fase live:)* el day trading intensivo en cuentas de margen US bajo US$25.000 cae bajo la regla **PDT** (límite de day trades). No afecta el desarrollo en paper.

---

## 7. Cómo encarar (criterio general, no pasos)

- **Por fases**, de lo más simple a lo más complejo. Prioridad sugerida a discutir: primero el **cerebro** (conexión a Tradier en sandbox + interfaz/adaptador + máquina de estados, probado por consola), porque es lo que define si el proyecto es viable; la **cara (GUI)** se le enchufa después.
- El proyecto debe vivir en una **carpeta local** desde el inicio (para poder abrirlo también desde otra herramienta si hiciera falta probar algo en el Windows real).
- Las **decisiones importantes** (de arquitectura o de qué construir) conviene dejarlas **escritas en archivos del proyecto** (este `.md` u otros), porque el chat de la herramienta no es memoria permanente.

---

## 8. Resumen de las reglas que más me importan

1. **Vos decidís lo técnico**; yo decido el qué/para qué. No me pases disyuntivas técnicas que no puedo evaluar.
2. **Cada autorización viene con una explicación simple** de qué buscás lograr.
3. **NUNCA dinero real durante el desarrollo. Todo en paper/sandbox.** Si algo pudiera tocar dinero real, **pedís autorización DETALLADA y RESALTADA** y esperás mi OK explícito.
4. **Explicá en lenguaje no técnico** lo que hacés.
5. Este documento es **contexto, no una orden de ejecutar**. El próximo paso es **acordar juntos un plan** antes de construir.
