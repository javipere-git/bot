"""
Donde se ejecuto cada operacion: quien la recibio y donde termino imprimiendo.

SON DOS COSAS DISTINTAS, y confundirlas es el error facil:

  A QUIEN SE LA DIERON  El broker le pasa la orden a alguien. Medido el
                        17/08/2026 sobre 346 operaciones, Tastytrade se la dio
                        SIEMPRE a un mayorista (Citadel, Hudson River,
                        Susquehanna, Virtu, Jane Street). Nunca directo a una
                        bolsa. Ese es su negocio: le vende el flujo.

  DONDE IMPRIMIO        Recien ahi el mayorista decide: se la queda el
                        (INTERNALIZADA) o la manda a un mercado. De esas 346:
                        286 se las quedaron (83%) y 58 salieron a una bolsa (17%).

Por eso una fila puede decir "Citadel -> Nasdaq": se la dieron a Citadel, y
Citadel la mando a Nasdaq. Y otra "Citadel -> Citadel": se la quedo.

EN LA CINTA (TAS): lo internalizado no imprime en ninguna bolsa, imprime fuera de
mercado y en la cinta consolidada aparece con la letra D (FINRA ADF). Medido en
vivo el 20/08/2026 con el feed de Tradier: de 446 prints, el 46% eran D. Con el
feed de Tastytrade, en cambio, no se ve NINGUNO: su streaming es solo Nasdaq
(1.782 prints capturados, 100% Q).
"""
from __future__ import annotations

# MIC del mercado donde imprimio -> (nombre legible, tipo)
# Los "mayoristas" son creadores de mercado que se quedan la operacion: es su
# propio MIC, no el de una bolsa.
_MERCADOS = {
    # se la quedo el mayorista (internalizada)
    "CDED": ("Citadel", "Internalizada"),
    "HRTF": ("Hudson River", "Internalizada"),
    "G1XX": ("Susquehanna", "Internalizada"),
    "JNST": ("Jane Street", "Internalizada"),
    "KNEM": ("Virtu", "Internalizada"),
    "KNLI": ("Virtu", "Internalizada"),
    "NITE": ("Virtu", "Internalizada"),
    "VIRT": ("Virtu", "Internalizada"),
    "UBSS": ("UBS", "Internalizada"),
    "TWSE": ("Two Sigma", "Internalizada"),
    "JPMS": ("JP Morgan", "Internalizada"),
    # bolsas de verdad (ahi la orden se ve en el libro)
    "XNAS": ("Nasdaq", "Mercado"),
    "XNYS": ("NYSE", "Mercado"),
    "ARCX": ("NYSE Arca", "Mercado"),
    "XASE": ("NYSE American", "Mercado"),
    "XCIS": ("NYSE National", "Mercado"),
    "XCHI": ("NYSE Chicago", "Mercado"),
    "EDGX": ("Cboe EDGX", "Mercado"),
    "EDGA": ("Cboe EDGA", "Mercado"),
    "BATS": ("Cboe BZX", "Mercado"),
    "BATY": ("Cboe BYX", "Mercado"),
    "MEMX": ("MEMX", "Mercado"),
    "IEXG": ("IEX", "Mercado"),
    "XBOS": ("Nasdaq BX", "Mercado"),
    "XPHL": ("Nasdaq PSX", "Mercado"),
    "EPRL": ("MIAX Pearl", "Mercado"),
    "LTSE": ("LTSE", "Mercado"),
    # mercados privados (ni bolsa ni mayorista)
    "INCR": ("Intelligent Cross", "ATS"),
    "LEVL": ("Level ATS", "ATS"),
    "MSPL": ("MS Pool", "ATS"),
    "UBSA": ("UBS ATS", "ATS"),
}


def describir(mic) -> tuple[str | None, str | None]:
    """(nombre legible, tipo) del mercado donde imprimio.

    Un MIC que no conocemos se devuelve tal cual y SIN tipo: preferimos una celda
    vacia antes que clasificarlo mal. Si aparece seguido, se agrega arriba."""
    codigo = str(mic or "").strip().upper()
    if not codigo:
        return (None, None)
    if codigo in _MERCADOS:
        return _MERCADOS[codigo]
    return (codigo, None)


def mayorista(destino) -> str | None:
    """El nombre del que recibio la orden, legible.

    Tasty lo manda como 'CITADEL_EQUITIES' o 'CITADEL_EQUITIES_A' (la letra del
    final es su sub-destino interno, no aporta nada)."""
    texto = str(destino or "").strip()
    if not texto:
        return None
    for cola in ("_EQUITIES", "_TRADING"):
        if cola in texto:
            texto = texto.split(cola)[0]
            break
    return texto.replace("_", " ").title()
