"""Reporte de una PASADA del bot (de Iniciar a Detener).

Junta contadores EN MEMORIA de todo lo que hizo el bot en una corrida: cuantas
acciones salteo cada filtro, cuantas entradas se llenaron con la Orden 1 y con la
Orden 2, por que nivel de salida cerro cada posicion, cuantas veces salto el
guardia, y con que configuracion corrio.

El NETO no se calcula aca: lo pone la pantalla por DIFERENCIA del "realizado" que
informa el broker entre el inicio y el fin de la pasada. Asi sale neto de
comisiones e incluye tambien los cierres que hiciste a mano. Ver main_window.

PRIORIDAD: contar no puede frenar ni trabar el bot. Todo son sumas de enteros en
memoria (nanosegundos) al lado de puntos donde el motor YA escribia en el log; no
agrega ni una sola llamada a la API. Y es defensivo: los metodos nunca lanzan, asi
que aunque algo saliera mal aca, el trading no se corta.

Extensible: si manana agregas un filtro nuevo, sumale una etiqueta en
NOMBRES_FILTROS y un solo conteo en el motor -> aparece solo en el reporte.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import (
    EngineConfig,
    GuardAction,
    GuardUnit,
    OffsetUnit,
    Side,
)

# Etiqueta legible de cada filtro, en el orden en que se muestran.
NOMBRES_FILTROS: dict[str, str] = {
    "spread_min": "Spread por debajo del minimo",
    "spread_max": "Spread por encima del maximo",
    "spread_pct_precio": "Spread demasiado ancho vs. el precio",
    "volumen_dia_min": "Volumen del dia por debajo del minimo",
    "volumen_dia_max": "Volumen del dia por encima del maximo",
    "cambios_bid": "El bid se movio demasiadas veces",
    "cambios_ask": "El ask se movio demasiadas veces",
    "spread_reciente": "El spread estuvo mucho mas ancho hace un rato",
    "volumen_reciente": "Demasiado volumen operado recien",
}


@dataclass
class SalidaInfo:
    """El detalle de una salida concreta (para listarlas)."""
    symbol: str
    nivel: int
    descripcion: str        # "cruzar el spread", "10% del spread", "0.02 USD"...


@dataclass
class ReportePasada:
    """Contadores de una pasada. Se crea al iniciar y se cierra al detener."""
    inicio: float = field(default_factory=time.time)   # epoch (para el rango horario)
    fin: float | None = None

    # ----- entradas -----
    llenados_orden1: int = 0
    llenados_orden2: int = 0
    uso_orden2: bool = False

    # ----- salidas -----
    salidas_por_nivel: dict[int, int] = field(default_factory=dict)
    salidas_cruzar: int = 0
    salidas_forzadas_guardia: int = 0
    detalle_salidas: list[SalidaInfo] = field(default_factory=list)

    # ----- guardia -----
    guardia_manual: int = 0          # veces que el guardia freno y paso a manual
    guardia_alarma_manual: int = 0   # alarmas que sono estando YA en manual

    # ----- filtros -----
    filtros: dict[str, int] = field(default_factory=dict)      # clave -> salteadas
    filtros_activos: set[str] = field(default_factory=set)     # cuales estaban puestos

    # ----- configuracion con la que corrio (texto ya armado) -----
    config_texto: str = ""

    # ----- neto (lo completa la pantalla) -----
    neto: float | None = None
    neto_disponible: bool = False

    # ---------- incrementos (defensivos: nunca lanzan) ----------
    def contar_filtro(self, clave: str) -> None:
        try:
            self.filtros[clave] = self.filtros.get(clave, 0) + 1
        except Exception:  # noqa: BLE001
            pass

    def contar_entrada(self, cual: int) -> None:
        try:
            if cual == 2:
                self.llenados_orden2 += 1
            else:
                self.llenados_orden1 += 1
        except Exception:  # noqa: BLE001
            pass

    def contar_salida(self, symbol: str, nivel: int, cross: bool, desc: str) -> None:
        try:
            self.salidas_por_nivel[nivel] = self.salidas_por_nivel.get(nivel, 0) + 1
            if cross:
                self.salidas_cruzar += 1
            self.detalle_salidas.append(SalidaInfo(symbol, nivel, desc))
        except Exception:  # noqa: BLE001
            pass

    def contar_salida_forzada(self) -> None:
        try:
            self.salidas_forzadas_guardia += 1
        except Exception:  # noqa: BLE001
            pass

    def contar_guardia_manual(self) -> None:
        try:
            self.guardia_manual += 1
        except Exception:  # noqa: BLE001
            pass

    def contar_guardia_alarma(self) -> None:
        try:
            self.guardia_alarma_manual += 1
        except Exception:  # noqa: BLE001
            pass

    # ---------- ayudas ----------
    @property
    def total_entradas(self) -> int:
        return self.llenados_orden1 + self.llenados_orden2

    @property
    def total_cerradas(self) -> int:
        return sum(self.salidas_por_nivel.values())

    def rango_horario(self) -> str:
        ini = time.strftime("%H:%M:%S", time.localtime(self.inicio))
        fin = time.strftime("%H:%M:%S", time.localtime(self.fin)) if self.fin else "..."
        return f"{ini} - {fin}"

    # ---------- guardar / leer como datos (para que sobrevivan al cierre) ----------
    def to_dict(self) -> dict:
        """Los numeros de la pasada como diccionario simple (para guardar en .json)."""
        return {
            "inicio": self.inicio,
            "fin": self.fin,
            "llenados_orden1": self.llenados_orden1,
            "llenados_orden2": self.llenados_orden2,
            "uso_orden2": self.uso_orden2,
            # las claves de un dict en JSON son texto: guardo el nivel como str
            "salidas_por_nivel": {str(k): v for k, v in self.salidas_por_nivel.items()},
            "salidas_cruzar": self.salidas_cruzar,
            "salidas_forzadas_guardia": self.salidas_forzadas_guardia,
            "detalle_salidas": [
                {"symbol": s.symbol, "nivel": s.nivel, "descripcion": s.descripcion}
                for s in self.detalle_salidas
            ],
            "guardia_manual": self.guardia_manual,
            "guardia_alarma_manual": self.guardia_alarma_manual,
            "filtros": dict(self.filtros),
            "filtros_activos": sorted(self.filtros_activos),
            "config_texto": self.config_texto,
            "neto": self.neto,
            "neto_disponible": self.neto_disponible,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReportePasada":
        """Reconstruye una pasada guardada. El llamador lo envuelve en try/except."""
        rep = cls(inicio=float(d.get("inicio") or time.time()))
        fin = d.get("fin")
        rep.fin = float(fin) if fin is not None else None
        rep.llenados_orden1 = int(d.get("llenados_orden1", 0))
        rep.llenados_orden2 = int(d.get("llenados_orden2", 0))
        rep.uso_orden2 = bool(d.get("uso_orden2", False))
        rep.salidas_por_nivel = {
            int(k): int(v) for k, v in (d.get("salidas_por_nivel") or {}).items()
        }
        rep.salidas_cruzar = int(d.get("salidas_cruzar", 0))
        rep.salidas_forzadas_guardia = int(d.get("salidas_forzadas_guardia", 0))
        rep.detalle_salidas = [
            SalidaInfo(x.get("symbol", ""), int(x.get("nivel", 0)),
                       x.get("descripcion", ""))
            for x in (d.get("detalle_salidas") or [])
        ]
        rep.guardia_manual = int(d.get("guardia_manual", 0))
        rep.guardia_alarma_manual = int(d.get("guardia_alarma_manual", 0))
        rep.filtros = {k: int(v) for k, v in (d.get("filtros") or {}).items()}
        rep.filtros_activos = set(d.get("filtros_activos") or [])
        rep.config_texto = d.get("config_texto", "")
        neto = d.get("neto")
        rep.neto = float(neto) if neto is not None else None
        rep.neto_disponible = bool(d.get("neto_disponible", False))
        return rep


# ============================ armado del texto de config ============================
def _u_offset(unit: OffsetUnit) -> str:
    return "% del spread" if unit == OffsetUnit.PERCENT_SPREAD else " USD"


def _u_guard(unit: GuardUnit) -> str:
    return "% del precio" if unit == GuardUnit.PERCENT else " USD"


def _accion_guard(a: GuardAction) -> str:
    return {
        GuardAction.MANUAL: "pasar a manual",
        GuardAction.FORCE_EXIT: "salir cruzando el spread",
        GuardAction.CONTINUE: "seguir con el escalonado",
    }.get(a, str(a))


def resumen_config(cfg: EngineConfig) -> str:
    """Texto legible con TODO lo que el bot tiene seteado en esta pasada."""
    L: list[str] = []
    lado = "Compra (largo)" if cfg.side == Side.BUY else "Venta en corto"
    L.append(f"Lado: {lado}")
    L.append(f"Cantidad por orden: {cfg.quantity} acciones")
    L.append(
        f"Orden 1: offset {cfg.order1.offset:g}{_u_offset(cfg.order1.unit)}, "
        f"timeout {cfg.order1.timeout_s:g}s"
    )
    if cfg.order2 is not None:
        L.append(
            f"Orden 2: offset {cfg.order2.offset:g}{_u_offset(cfg.order2.unit)}, "
            f"timeout {cfg.order2.timeout_s:g}s"
        )
    else:
        L.append("Orden 2: no se usa")
    L.append(f"Duracion: {cfg.duration.value}"
             + ("  (extended hours ON)" if cfg.extended_hours else ""))

    # filtros
    fil: list[str] = []
    if cfg.spread_min is not None:
        fil.append(f"spread minimo {cfg.spread_min:g}")
    if cfg.spread_max is not None:
        fil.append(f"spread maximo {cfg.spread_max:g}")
    if cfg.max_spread_pct_precio is not None:
        fil.append(f"spread {cfg.max_spread_pct_precio:g}% del precio o mas")
    if cfg.volume_min is not None:
        fil.append(f"volumen dia min {cfg.volume_min:,}")
    if cfg.volume_max is not None:
        fil.append(f"volumen dia max {cfg.volume_max:,}")
    if cfg.max_cambios_bid is not None:
        fil.append(f"cambios bid max {cfg.max_cambios_bid} en {cfg.ventana_bid_s:g}s")
    if cfg.max_cambios_ask is not None:
        fil.append(f"cambios ask max {cfg.max_cambios_ask} en {cfg.ventana_ask_s:g}s")
    if cfg.max_spread_pct is not None:
        fil.append(f"spread reciente max {cfg.max_spread_pct:g}% del actual "
                   f"en {cfg.ventana_spread_s:g}s")
    if cfg.max_volumen_seg is not None:
        fil.append(f"volumen reciente max {cfg.max_volumen_seg:,} "
                   f"en {cfg.ventana_volumen_s:g}s")
    L.append("Filtros: " + ("; ".join(fil) if fil else "ninguno"))

    # salidas
    niveles = [lv for lv in cfg.exit_levels if lv.enabled]
    if niveles:
        for i, lv in enumerate(niveles, 1):
            if lv.cross:
                L.append(f"Salida nivel {i}: cruzar el spread, timeout {lv.timeout_s:g}s")
            else:
                L.append(f"Salida nivel {i}: offset {lv.offset:g}{_u_offset(lv.unit)}, "
                         f"timeout {lv.timeout_s:g}s")
    else:
        L.append("Salidas: ninguna (queda en manual)")

    # guardia
    g = cfg.guard
    if g is not None and g.enabled:
        L.append(f"Guardia: umbral {g.threshold:g}{_u_guard(g.unit)} -> {_accion_guard(g.action)}")
    else:
        L.append("Guardia: desactivado")

    return "\n".join(L)


# ============================ armado del texto del reporte ============================
def _dur(seg: float) -> str:
    seg = int(max(0, seg))
    m, s = divmod(seg, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _linea_neto(rep: ReportePasada) -> str:
    if rep.neto_disponible and rep.neto is not None:
        signo = "+" if rep.neto >= 0 else ""
        return (f"Neto de la pasada: {signo}{rep.neto:.2f} USD"
                "   (realizado del broker, neto de comisiones)")
    return "Neto de la pasada: no disponible (no pude leer el resultado del broker)"


def _bloque_salidas(rep: ReportePasada) -> list[str]:
    L = ["=== SALIDAS ==="]
    if rep.salidas_por_nivel:
        for nivel in sorted(rep.salidas_por_nivel):
            L.append(f"  Nivel {nivel}: {rep.salidas_por_nivel[nivel]}")
        L.append(f"  De esas, cerraron cruzando el spread: {rep.salidas_cruzar}")
    else:
        L.append("  Ninguna posicion cerro por un nivel de salida.")
    L.append(f"  Salidas forzadas por el guardia: {rep.salidas_forzadas_guardia}")
    return L


def _bloque_filtros(rep: ReportePasada) -> list[str]:
    L = ["=== FILTROS (acciones salteadas) ==="]
    if not rep.filtros_activos:
        L.append("  No habia filtros configurados en esta pasada.")
        return L
    for clave, etiqueta in NOMBRES_FILTROS.items():
        if clave in rep.filtros_activos:
            L.append(f"  {etiqueta}: {rep.filtros.get(clave, 0)}")
    # por si aparece una clave contada que no este en el catalogo (filtro nuevo sin
    # etiqueta todavia): la mostramos igual, no la escondemos
    for clave, n in rep.filtros.items():
        if clave not in NOMBRES_FILTROS:
            L.append(f"  {clave}: {n}")
    return L


def render_pasada(rep: ReportePasada) -> str:
    """Texto completo de UNA pasada, con entrada/salida/guardia primero."""
    dur = _dur((rep.fin or time.time()) - rep.inicio)
    L: list[str] = []
    L.append("REPORTE DE PASADA DEL BOT")
    L.append(f"Horario: {rep.rango_horario()}   (duracion {dur})")
    L.append("")
    # --- bloque destacado: resultado + entradas + salidas + guardia ---
    L.append(_linea_neto(rep))
    L.append("")
    L.append("=== ENTRADAS ===")
    L.append(f"  Llenados con la Orden 1: {rep.llenados_orden1}")
    if rep.uso_orden2:
        L.append(f"  Llenados con la Orden 2: {rep.llenados_orden2}")
    else:
        L.append("  Orden 2: no se uso en esta pasada")
    L.append(f"  Total de entradas: {rep.total_entradas}")
    L.append("")
    L += _bloque_salidas(rep)
    L.append("")
    L.append("=== GUARDIA DE MOVIMIENTO ===")
    L.append(f"  Veces que freno y paso a manual: {rep.guardia_manual}")
    L.append(f"  Alarmas estando ya en manual: {rep.guardia_alarma_manual}")
    L.append("")
    # --- luego los filtros ---
    L += _bloque_filtros(rep)
    L.append("")
    # --- y al final la config con la que corrio ---
    L.append("=== CONFIGURACION DE ESTA PASADA ===")
    L.append(rep.config_texto or "  (no registrada)")
    L.append("")
    return "\n".join(L)


def render_resumen_dia(reps: list[ReportePasada]) -> str:
    """Suma de TODAS las pasadas del dia."""
    if not reps:
        return "RESUMEN DEL DIA\n\nTodavia no hay pasadas registradas hoy.\n"

    o1 = sum(r.llenados_orden1 for r in reps)
    o2 = sum(r.llenados_orden2 for r in reps)
    uso_o2 = any(r.uso_orden2 for r in reps)
    forzadas = sum(r.salidas_forzadas_guardia for r in reps)
    cruzar = sum(r.salidas_cruzar for r in reps)
    g_manual = sum(r.guardia_manual for r in reps)
    g_alarma = sum(r.guardia_alarma_manual for r in reps)

    por_nivel: dict[int, int] = {}
    for r in reps:
        for nivel, n in r.salidas_por_nivel.items():
            por_nivel[nivel] = por_nivel.get(nivel, 0) + n

    filtros: dict[str, int] = {}
    activos: set[str] = set()
    for r in reps:
        activos |= r.filtros_activos
        for clave, n in r.filtros.items():
            filtros[clave] = filtros.get(clave, 0) + n

    netos = [r.neto for r in reps if r.neto_disponible and r.neto is not None]
    neto_total = sum(netos) if netos else None
    todos_con_neto = len(netos) == len(reps)

    ini = time.strftime("%d/%m/%Y", time.localtime(reps[0].inicio))
    L: list[str] = []
    L.append(f"RESUMEN DEL DIA  ({ini})")
    L.append(f"Pasadas: {len(reps)}")
    L.append("")
    if neto_total is not None:
        signo = "+" if neto_total >= 0 else ""
        aclara = "" if todos_con_neto else "  (algunas pasadas sin neto disponible)"
        L.append(f"Neto del dia: {signo}{neto_total:.2f} USD{aclara}")
    else:
        L.append("Neto del dia: no disponible")
    L.append("")
    L.append("=== ENTRADAS ===")
    L.append(f"  Llenados con la Orden 1: {o1}")
    L.append(f"  Llenados con la Orden 2: {o2}" if uso_o2
             else "  Orden 2: no se uso en el dia")
    L.append(f"  Total de entradas: {o1 + o2}")
    L.append("")
    L.append("=== SALIDAS ===")
    if por_nivel:
        for nivel in sorted(por_nivel):
            L.append(f"  Nivel {nivel}: {por_nivel[nivel]}")
        L.append(f"  De esas, cerraron cruzando el spread: {cruzar}")
    else:
        L.append("  Ninguna posicion cerro por un nivel de salida.")
    L.append(f"  Salidas forzadas por el guardia: {forzadas}")
    L.append("")
    L.append("=== GUARDIA DE MOVIMIENTO ===")
    L.append(f"  Veces que freno y paso a manual: {g_manual}")
    L.append(f"  Alarmas estando ya en manual: {g_alarma}")
    L.append("")
    L.append("=== FILTROS (acciones salteadas) ===")
    if activos:
        for clave, etiqueta in NOMBRES_FILTROS.items():
            if clave in activos:
                L.append(f"  {etiqueta}: {filtros.get(clave, 0)}")
        for clave, n in filtros.items():
            if clave not in NOMBRES_FILTROS:
                L.append(f"  {clave}: {n}")
    else:
        L.append("  No hubo filtros configurados en el dia.")
    L.append("")
    L.append("=== DETALLE POR PASADA ===")
    for i, r in enumerate(reps, 1):
        if r.neto_disponible and r.neto is not None:
            signo = "+" if r.neto >= 0 else ""
            neto = f"{signo}{r.neto:.2f} USD"
        else:
            neto = "neto n/d"
        L.append(f"  {i}. {r.rango_horario()}   entradas {r.total_entradas}   "
                 f"cerradas {r.total_cerradas}   {neto}")
    L.append("")
    return "\n".join(L)
