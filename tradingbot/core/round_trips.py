"""
Armar los TRADES CERRADOS (round trips) a partir de las ejecuciones.

Una ejecucion suelta no dice como te fue: "compre 20 ULH a 19,68" no es ni ganancia
ni perdida hasta que las vendes. El round trip junta la entrada con su salida y
recien ahi hay un resultado.

POR QUE SE CALCULA ACA Y NO SE LE PIDE AL BROKER: solo Tradier lo ofrece hecho
(endpoint gainloss). Alpaca y Tasty no. Calcularlo nosotros da el MISMO criterio en
los tres, y sale de las ejecuciones que ya bajamos: cero llamadas de mas.

EL CRITERIO ES FIFO: la primera que compraste es la primera que se cierra. Es el
que usan los brokers y el fisco de EE.UU. por defecto. Ejemplo: comprás 10 a $50,
comprás 10 a $60 y vendés 10 a $70 -> el trade cerrado es contra las de $50
(ganancia $200), y quedan 10 abiertas a $60.

Sirve igual para cortos: una venta sin posicion abre un corto, y la compra
posterior lo cierra. El resultado se da vuelta (ganas si baja).

UNA ADVERTENCIA CON TRADIER: su historial trae la FECHA pero no la HORA, asi que
dentro de un mismo dia el unico orden que hay es el que manda la API. Si un dia
operaste el mismo simbolo mas de una vez, la etiqueta Largo/Corto puede salir
dada vuelta. La PLATA no cambia: comprar a 10 y vender a 11 da lo mismo que
vender a 11 y recomprar a 10. Verificado el 17/08/2026 contra un calculo
independiente (la suma de la plata que entro y salio de la cuenta): 3.628
ejecuciones, todo cerrado, +2.386,91 de neto contra +2.525,64 de bruto nuestro.
La diferencia son las comisiones, y el total no depende del orden.
"""
from __future__ import annotations

from collections import deque

COLUMNAS = [
    ("symbol", "Simbolo"),
    ("lado", "Lado"),
    ("cantidad", "Cantidad"),
    ("entrada", "Entrada"),
    ("precio_entrada", "Precio entrada"),
    ("salida", "Salida"),
    ("precio_salida", "Precio salida"),
    ("resultado", "Resultado"),
    ("resultado_pct", "Resultado %"),
    ("costos", "Comisiones y tasas"),
    ("resultado_neto", "Resultado neto"),
    ("duracion", "Duracion"),
]

_COMPRAS = ("Compra", "Compra (abre)", "Compra (cierra el corto)")


def _es_compra(lado) -> bool:
    """El lado viene en castellano desde el conector. Tasty ademas aclara si abre o
    cierra, pero para aparear alcanza con saber si sumo o resto acciones."""
    return str(lado or "").startswith("Compra")


def _costo_por_accion(fila) -> float:
    """Comisiones y tasas de esa ejecucion, repartidas por accion.

    Se reparten porque una ejecucion de 100 acciones puede cerrar dos trades de 50.
    Si el broker no las informa (Alpaca), da 0: no se inventa un costo."""
    cant = float(fila.get("cantidad") or 0)
    if not cant:
        return 0.0
    total = abs(float(fila.get("comision") or 0)) + abs(float(fila.get("tasas") or 0))
    return total / cant


def _duracion(entrada: str, salida: str) -> str:
    """Cuanto duro el trade, en texto corto. Si el broker no informa la hora
    (Tradier), se cuenta en dias."""
    if not entrada or not salida:
        return ""
    if len(entrada) <= 10 or len(salida) <= 10:
        from datetime import date
        try:
            d = (date.fromisoformat(salida[:10]) - date.fromisoformat(entrada[:10])).days
        except ValueError:
            return ""
        return "mismo dia" if d == 0 else f"{d} dia(s)"
    from datetime import datetime
    try:
        seg = (datetime.fromisoformat(salida) - datetime.fromisoformat(entrada)).total_seconds()
    except ValueError:
        return ""
    if seg < 60:
        return f"{seg:.0f} s"
    if seg < 3600:
        return f"{seg / 60:.1f} min"
    if seg < 86400:
        return f"{seg / 3600:.1f} h"
    return f"{seg / 86400:.1f} dias"


def armar(ejecuciones) -> tuple[list[dict], list[dict]]:
    """Devuelve (trades cerrados, lo que quedo abierto).

    Lo que quedo abierto se devuelve aparte a proposito: si en el periodo compraste
    y todavia no vendiste, eso NO es un resultado, y meterlo en la misma lista con
    un cero seria mentir. Sirve para avisar cuantas quedaron colgadas."""
    en_orden = sorted(ejecuciones, key=lambda f: str(f.get("fecha_hora") or ""))
    abiertas: dict[str, deque] = {}
    cerrados: list[dict] = []

    for f in en_orden:
        sym = f.get("symbol") or ""
        queda = abs(float(f.get("cantidad") or 0))
        if not queda:
            continue
        precio = float(f.get("precio") or 0)
        fecha = str(f.get("fecha_hora") or "")
        compra = _es_compra(f.get("lado"))
        costo_u = _costo_por_accion(f)
        cola = abiertas.setdefault(sym, deque())

        while queda > 0:
            if not cola or cola[0]["compra"] == compra:
                # nada que cerrar (o va en la misma direccion): queda abierta
                cola.append({"compra": compra, "cantidad": queda, "precio": precio,
                             "fecha": fecha, "costo_u": costo_u})
                break
            lote = cola[0]
            usa = min(queda, lote["cantidad"])
            # el que estaba primero es la ENTRADA; el que llega ahora, la SALIDA
            largo = lote["compra"]
            p_ent, p_sal = lote["precio"], precio
            bruto = (p_sal - p_ent) * usa * (1 if largo else -1)
            costos = -(lote["costo_u"] + costo_u) * usa
            invertido = p_ent * usa
            cerrados.append({
                "symbol": sym,
                "lado": "Largo" if largo else "Corto",
                "cantidad": usa,
                "entrada": lote["fecha"],
                "precio_entrada": round(p_ent, 6),
                "salida": fecha,
                "precio_salida": round(p_sal, 6),
                "resultado": round(bruto, 2),
                "resultado_pct": round(bruto / invertido * 100, 2) if invertido else None,
                "costos": round(costos, 4) if costos else None,
                "resultado_neto": round(bruto + costos, 2) if costos else None,
                "duracion": _duracion(lote["fecha"], fecha),
            })
            lote["cantidad"] -= usa
            queda -= usa
            if lote["cantidad"] <= 0:
                cola.popleft()

    sueltas = [
        {"symbol": sym, "lado": "Largo" if l["compra"] else "Corto",
         "cantidad": l["cantidad"], "entrada": l["fecha"],
         "precio_entrada": round(l["precio"], 6)}
        for sym, cola in abiertas.items() for l in cola if l["cantidad"] > 0
    ]
    return cerrados, sueltas


def resumen(cerrados, sueltas=()) -> str:
    """Una linea para el registro."""
    if not cerrados:
        return "no se cerro ningun trade en esas fechas"
    ganadores = [t for t in cerrados if t["resultado"] > 0]
    total = sum(t["resultado"] for t in cerrados)
    texto = (f"{len(cerrados):,} trade(s) cerrado(s), "
             f"{len(ganadores):,} en ganancia ({len(ganadores) / len(cerrados):.0%}), "
             f"resultado bruto {total:+,.2f}")
    if sueltas:
        texto += f". Quedaron {len(sueltas):,} punta(s) sin cerrar en el periodo"
    return texto
