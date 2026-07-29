# Propuesta: que la app soporte varios brokers

**Objetivo:** que la app pueda conectarse a distintos brokers (se elige al abrir),
y que **sumar un broker nuevo sea escribir un archivo**, sin tocar el resto.
Hoy somos tres queriendo enchufar brokers distintos (Alpaca ya esta, Tradier y uno
mas en camino), asi que conviene acordar el camino ANTES de que cada uno arranque
por su cuenta.

---

## Lo que hay hoy (numeros reales del codigo)

Mire `trading_app.py` (7.521 lineas) y `tas_module.py` (1.295). Lo que encontre:

| Que | Cuanto |
|---|---|
| Lugares que **crean** clientes de Alpaca | 8 |
| **Llamadas** a operaciones (mandar orden, cancelar, precios...) | 18 |
| Lugares que usan **campos con forma de Alpaca** (`.qty`, `.side`, `.status`, `.limit_price`, `.filled_qty`...) | ~70 |
| Usos de **enums de Alpaca** (`OrderSide.BUY`, `OrderStatus.FILLED`, `TimeInForce.DAY`...) | 44 |
| **Lineas de import** por las que entra TODO lo de Alpaca | ~11 (juntas, arriba del archivo) |

Dos conclusiones:

1. **No hay una capa que separe el broker**: la app le habla a Alpaca directo.
2. Pero esta **ordenado**: las llamadas estan concentradas y, sobre todo,
   **todo lo de Alpaca entra por 11 lineas de import al principio**. Eso ultimo es
   la clave de la propuesta.

**Operaciones que la app realmente necesita de un broker** (el "contrato"):

- Ordenes: mandar, reemplazar/repreciar, cancelar una, cancelar todas, listar
- Cuenta: posiciones, datos de la cuenta (equity, buying power), simbolos operables
- Datos: ultimo quote, snapshot, barras (para el grafico)
- Streaming: precios en vivo y avisos de ejecucion

Son ~14 cosas. Ese es el contrato que tendria que cumplir cada broker.

---

## Las tres opciones

### Opcion A — "un broker disfrazado de Alpaca"

Cada broker nuevo se escribe **imitando por fuera a la libreria de Alpaca** (mismos
nombres de metodos, mismos campos). La app ni se entera.

- **A favor:** es la mas barata para UN broker: se tocan ~8 lugares.
- **En contra (y es grave para este objetivo):** **el contrato no esta escrito en
  ningun lado.** Es "portate como se porta alpaca-py". Nadie sabe donde termina eso:
  ¿que subconjunto?, ¿que excepciones?, ¿que enums?. Con dos personas se maneja; con
  tres, cada uno adivina un contrato distinto y terminamos con tres apps que no se
  pueden juntar. Ademas ata el diseño a los caprichos de una libreria de terceros.

### Opcion B — reestructurar la app con una capa de brokers

Definir un modelo neutro propio (nombres nuevos) y adaptar toda la app.

- **A favor:** es el diseño "de manual", explicito y prolijo.
- **En contra:** hay que tocar **~140 lugares** del archivo principal (los ~70 campos
  + los 44 enums + las llamadas). Es mucho trabajo, mucho riesgo de romper algo que
  hoy funciona, y todo ese cambio recae sobre el codigo de Mariano. Costo alto para
  un beneficio que se puede conseguir mas barato (ver A+).

### Opcion A+ — contrato explicito, PERO con los nombres que la app ya usa ✅

La idea: escribir un **contrato propio y documentado** (una interfaz: "un broker debe
saber hacer estas ~14 cosas"), y que **los nombres de los campos y enums sean los
mismos que la app ya usa hoy** (`qty`, `side`, `status`, `limit_price`, `OrderSide.BUY`...).

Por que esto es barato: como los nombres coinciden, **los ~140 lugares no se tocan**.
Solo hay que:

1. Crear un paquete nuevo `brokers/` con:
   - el contrato + los modelos y enums (con los nombres actuales),
   - `alpaca.py` (envuelve lo que ya existe; casi todo pasa derecho),
   - `tradier.py`, y el que sume cada uno.
2. Cambiar las **~11 lineas de import** para que apunten a `brokers/` en vez de a
   `alpaca...`.
3. Cambiar los **8 lugares** que crean el cliente, para que pidan el broker elegido.
4. Agregar el selector de broker al abrir.

**Total: ~20 lugares tocados, no 140.** El codigo de Mariano queda practicamente
intacto y, aun asi, queda un contrato explicito y escrito.

---

## Por que recomiendo A+

| | Trabajo sobre el archivo de Mariano | Sirve para 3+ brokers | Contrato claro |
|---|---|---|---|
| **A** | ~8 lugares | Fragil | ❌ implicito |
| **B** | ~140 lugares | Si | ✅ |
| **A+** | **~20 lugares** | **Si** | ✅ |

A+ da el beneficio de B al costo de A. Y para el objetivo de "sumar brokers de a
uno, entre varios", lo que realmente importa es que **exista un contrato escrito**:
el que suma un broker implementa esas ~14 cosas y no necesita leer las 7.500 lineas
ni adivinar nada.

Nota: esta arquitectura ya esta probada. La app de Javier se hizo asi (contrato +
un archivo por broker) y cuando hubo que sumar un segundo broker, fue escribir un
solo archivo. Tambien salieron a la luz las diferencias entre brokers que conviene
tener contempladas en el contrato desde el dia uno:

- lo que un broker llama "modificar una orden", otro lo resuelve **cancelando y
  creando una nueva con otro ID** (si no se contempla, quedan ordenes huerfanas vivas),
- los limites de llamadas por minuto son muy distintos y se agotan de formas distintas,
- no todos entregan la misma informacion (dia operativo, horario extendido, overnight),
- no todos distinguen "vender" de "vender en corto".

---

## Lo que habria que acordar entre los tres

1. **Ir por A+** (o discutirlo, pero decidir algo antes de escribir codigo).
2. **Quien escribe el contrato** (`brokers/base.py`) y los cambios en el archivo
   principal. Conviene que sea UNA sola persona, para que salga coherente.
3. Recien despues, **cada uno escribe su broker en paralelo**, sin pisarse: cada
   broker es un archivo nuevo e independiente.
4. **Una rama por tema** (`contrato-brokers`, `broker-tradier`, `broker-xxx`), asi
   se revisan y se incorporan por separado.

El punto 2 es el que hay que resolver primero: mientras no exista el contrato, los
demas no pueden empezar sin riesgo de tirar el trabajo.
