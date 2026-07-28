# Bot de trading + Ladder (multi-broker)

Aplicacion de escritorio de trading, multi-broker desde el diseño.
**Brokers cableados: Tradier y Alpaca** (mas el conector "hibrido", que opera en un
broker tomando los precios del otro).

| Documento | Para que |
|---|---|
| `MANUAL.md` | Manual de uso + condiciones de las APIs + bugs aprendidos |
| `INSTALAR_EN_OTRA_PC.md` | Poner la app a andar en otra computadora |
| `DECISIONES.md` | Por que se eligio cada cosa |
| `PENDIENTES.md` / `LISTA_DE_DESEOS.md` | Que falta / ideas futuras |
| `CONTEXTO_proyecto.md` | Briefing original del proyecto |

## Regla de oro
El desarrollo y las pruebas se hacen en **paper / sandbox (dinero simulado)**. Los
modos LIVE (dinero real) existen pero quedan **deshabilitados** hasta que el usuario
pega sus credenciales reales en `config/credentials.ini`, y tienen salvaguardas:
no-doble-posicion, tope de tamano (`live_max_shares`), doble confirmacion (escribir
REAL + cartel al iniciar) y aviso previo si la cuenta no permite operar en corto.
PAPER es siempre lo que aparece primero.

## Estructura
- `tradingbot/core/` — el "cerebro": motor (`engine.py`), modelos (`models.py`),
  configuracion (`config.py`) y la interfaz comun de brokers (`broker.py`).
- `tradingbot/connectors/` — los "traductores" a cada broker: `tradier.py`,
  `alpaca.py`, `hibrido.py`, `fake_broker.py` (simulado, para los tests) y los
  streamings (`*_stream.py`).
- `tradingbot/gui/` — la pantalla (PySide6): control, monitoreo, ladder, perfiles.
- `examples/` — demos y pruebas de integracion para correr por consola.
- `config/` — plantilla de credenciales (los tokens reales NO se suben al repo).

## Que NO esta en el repo (a proposito)
- `config/credentials.ini` — tus tokens. Es propio de cada maquina.
- `registro_*.log` — los registros de actividad.
- `referencia_marian/` — codigo de referencia visual, propiedad de su autor.

## Estado actual
- [x] Fase 0: estructura del proyecto.
- [x] Fase 1: interfaz comun + conector de mentira (probado por consola).
- [x] Fase 2: conectar a Tradier sandbox (solo lectura).
- [x] Fase 3: el cerebro completo (entrada + salida + guardia), probado con el conector de mentira.
  - [x] Tanda 1: la entrada (watchlist, filtro de spread, Orden 1 -> Orden 2, deteccion de llenado).
  - [x] Tanda 2: la salida (cierre escalonado de 4 niveles + guardia de movimiento en contra).
- [x] Fase 4: streaming de PRECIOS en vivo (market data, token de produccion solo lectura) alimentando el ladder. (Avisos de cuenta/fills por streaming: N/A en sandbox -> los fills del bot se detectan por polling REST.)
- [x] Fase 5: la cara (interfaz grafica con PySide6) - COMPLETA.
  - [x] Esqueleto: ventana con banner PAPER + 3 zonas (control / monitoreo / ladder) con divisores arrastrables.
  - [x] Panel de control cableado al motor: Iniciar/Pausar/Reanudar/Detener (bot en hilo aparte), log en vivo.
  - [x] Monitoreo: Posiciones, Ordenes abiertas, Ejecutadas y Canceladas (conteos/ratio), P/L abierto y secciones colapsables, en vivo. (P/L del dia con realizado: mejora futura.)
  - [x] Ladder: escalera + zoom + filas compactas + sizes + marketables + click-para-operar + mis ordenes dibujadas (cancelar al click) + marca de promedio + arrastrar orden para modificar precio.
- [x] Fase 6: robustez en vivo - COMPLETA (refinamientos planeados): 3 strikes -> frena solo; capa anti-caida; freno por desconexion; sonido en alertas; aviso de posicion abierta al reabrir; simbolo no operable -> saltea; indicador de conexion del streaming en el encabezado; ordenes fantasma (cancelar/llenarse) detectadas. Queda validarla con uso en paper. El modo LIVE (dinero real) NO existe todavia: requiere decision explicita del usuario + salvaguardas (ver PENDIENTES.md).

## Probar la demo (no toca dinero ni se conecta a nada)
```
python examples/demo_fake.py
```

## Instalacion de dependencias (por fase)
Las librerias externas se instalan cuando hacen falta:
- Fase 2 (Tradier REST): `pip install requests`
- Fase 4 (streaming): `pip install websocket-client`
- Fase 5 (interfaz grafica): `pip install PySide6`
