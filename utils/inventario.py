"""
utils/inventario.py — Helpers pequeños de inventario compartidos entre cogs.
"""


def tiene_telefono(datos: dict) -> bool:
    """True si el personaje tiene un teléfono (básico o smartphone) en su inventario."""
    inv = datos.get("inventario", {})
    return any("telefono" in i or "smartphone" in i for i in inv)
