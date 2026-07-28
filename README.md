# Bot de trading + Ladder (Tradier)

Aplicacion de escritorio de trading para Tradier, pensada para ser multi-broker.
Briefing completo en `CONTEXTO_proyecto.md`. Decisiones acordadas en `DECISIONES.md`.
Manual de uso + condiciones de la API de Tradier en `MANUAL.md`.

## Regla de oro
Todo el desarrollo se hace en **paper / sandbox (dinero simulado)**. El modo LIVE
(dinero real) existe pero queda deshabilitado hasta que el usuario pega su numero de
cuenta real en `config/credentials.ini`, y tiene salvaguardas: no-doble-posicion,
tope de tamano (`live_max_shares`), y doble confirmacion (escribir REAL + cartel al
iniciar). PAPER es siempre el modo por defecto.

## Estructura
- `tradingbot/core/` — el "cerebro": modelos de datos (`models.py`) y la interfaz comun (`broker.py`).
- `tradingbot/connectors/` — los "conectores": traductores a cada broker. Por ahora `fake_broker.py` (simulado). Mas adelante, Tradier.
- `examples/` — demos para probar por consola.
- `config/` — plantilla de credenciales (los tokens reales no se suben al repo).

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
