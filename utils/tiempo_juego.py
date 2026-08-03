"""
utils/tiempo_juego.py — Calendario del RP.

El rol empieza el 4 de enero de 2022 y el tiempo avanza más rápido que el real.
Por defecto 1 día de juego = 2 horas reales (configurable con HORAS_POR_DIA en
el .env), así que una semana de juego pasa en unas 14 horas reales y las
elecciones "cada 4 semanas" caen cada ~2 días y medio reales.

Todo (noticias, elecciones, eventos) usa esta única fuente de verdad para que
las fechas sean coherentes entre sistemas.
"""
import os
from datetime import datetime, timedelta

from utils import db

FECHA_INICIO_RP = datetime(2022, 1, 4)
HORAS_REALES_POR_DIA_JUEGO = float(os.getenv("HORAS_POR_DIA", "2"))

MESES_ES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


async def _ancla() -> float:
    """Timestamp real en que arrancó el RP. Se guarda la primera vez."""
    registro = await db.get("estado", "tiempo_juego")
    if registro and registro.get("ancla_ts"):
        return registro["ancla_ts"]
    import time as _t
    ahora = _t.time()
    await db.set("estado", "tiempo_juego", {"ancla_ts": ahora})
    return ahora


async def fecha_actual() -> datetime:
    """Fecha actual DENTRO del rol."""
    import time as _t
    ancla = await _ancla()
    horas_reales = (_t.time() - ancla) / 3600
    dias_juego = horas_reales / HORAS_REALES_POR_DIA_JUEGO
    return FECHA_INICIO_RP + timedelta(days=dias_juego)


async def dias_transcurridos() -> int:
    f = await fecha_actual()
    return (f - FECHA_INICIO_RP).days


async def semanas_transcurridas() -> int:
    return (await dias_transcurridos()) // 7


def formatear(f: datetime) -> str:
    return f"{DIAS_ES[f.weekday()]} {f.day} de {MESES_ES[f.month - 1]} de {f.year}"


async def fecha_texto() -> str:
    return formatear(await fecha_actual())


async def adelantar_dias(dias: float):
    """[ADMIN] Mueve el reloj del rol hacia adelante (o atrás con negativo)."""
    registro = await db.get("estado", "tiempo_juego") or {}
    ancla = registro.get("ancla_ts")
    if ancla is None:
        ancla = await _ancla()
    nueva = ancla - dias * HORAS_REALES_POR_DIA_JUEGO * 3600
    registro["ancla_ts"] = nueva
    await db.set("estado", "tiempo_juego", registro)
