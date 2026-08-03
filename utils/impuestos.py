"""
utils/impuestos.py — Sistema de impuestos compartido.

Centraliza TODAS las tasas de impuestos del servidor (para que sea fácil
ajustarlas desde un solo lugar) y un "tesoro nacional" donde va a parar cada
impuesto cobrado, sin importar de qué sistema venga (tienda, empresas,
bancos...). Así el Estado del RP tiene un número real y consultable en vez de
que los impuestos simplemente desaparezcan.
"""
from utils import db

# ── IVA por categoría de producto (aplicado en /comprar) ────────────────────
# Los alimentos y medicinas tienen tasa reducida (como en la vida real);
# los bienes de lujo/peligrosos tienen tasa alta.
IVA_CATEGORIA = {
    "comida":      0.06,
    "medicina":    0.02,
    "documento":   0.00,   # trámites del Estado, exentos
    "herramienta": 0.12,
    "hogar":       0.12,
    "ropa":        0.14,
    "misc":        0.14,
    "tech":        0.18,
    "vehiculo":    0.25,   # impuesto de lujo
    "arma":        0.30,   # impuesto más alto de todos
}
IVA_DEFAULT = 0.10  # categorías no listadas

# ── Impuesto corporativo por tipo de empresa (aplicado en ingresos) ─────────
IMPUESTO_CORPORATIVO = {
    "comercio":  0.12,
    "industria": 0.18,
    "tech":      0.22,
}
IMPUESTO_CORPORATIVO_DEFAULT = 0.15

# ── Impuesto a dividendos (cuando el dueño retira capital de su empresa) ────
IMPUESTO_DIVIDENDOS = 0.05


def tasa_iva(categoria: str) -> float:
    return IVA_CATEGORIA.get(categoria, IVA_DEFAULT)


def tasa_corporativa(tipo_empresa: str) -> float:
    return IMPUESTO_CORPORATIVO.get(tipo_empresa, IMPUESTO_CORPORATIVO_DEFAULT)


async def recaudar(monto: float, concepto: str = "general"):
    """Suma dinero al tesoro nacional. Se le puede llevar la cuenta por concepto."""
    if monto <= 0:
        return
    estado = await db.get("estado", "tesoro_nacional") or {"total": 0.0, "por_concepto": {}}
    estado["total"] = round(estado.get("total", 0.0) + monto, 2)
    por_concepto = estado.setdefault("por_concepto", {})
    por_concepto[concepto] = round(por_concepto.get(concepto, 0.0) + monto, 2)
    await db.set("estado", "tesoro_nacional", estado)


async def obtener_tesoro() -> dict:
    return await db.get("estado", "tesoro_nacional") or {"total": 0.0, "por_concepto": {}}
