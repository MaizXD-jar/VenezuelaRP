"""
utils/ia.py — Capa de IA compartida para todo el bot (mapa, NPCs, noticias).

Soporta VARIOS proveedores y va cayendo al siguiente si uno falla, se queda
sin cuota, o no está configurado:

1. GROQ    (recomendado) — gratis, MUY rápido, límites generosos.
   Key gratis en: https://console.groq.com/keys      → GROQ_API_KEY en .env
2. GEMINI  — gratis con límite diario menor.
   Key gratis en: https://aistudio.google.com/apikey  → GEMINI_API_KEY en .env
3. MISTRAL — gratis (tier "La Plateforme" free), buen respaldo si los otros
   dos se quedan sin cuota el mismo día.
   Key gratis en: https://console.mistral.ai/api-keys → MISTRAL_API_KEY en .env

Puedes poner cualquier combinación de las tres. El orden de intento es
siempre Groq → Gemini → Mistral, saltando automáticamente las que no tengan
key configurada o que devuelvan error/cuota agotada.
"""
from __future__ import annotations

import os
import asyncio

import aiohttp

# ── Groq ─────────────────────────────────────────────────────────────────────
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELOS_GROQ = [m for m in [
    os.getenv("GROQ_MODEL", "").strip(),
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
] if m]

# ── Gemini ───────────────────────────────────────────────────────────────────
MODELOS_GEMINI = [m for m in [
    os.getenv("GEMINI_MODEL", "").strip(),
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
] if m]

# ── Mistral (gratis) ──────────────────────────────────────────────────────────
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"
MODELOS_MISTRAL = [m for m in [
    os.getenv("MISTRAL_MODEL", "").strip(),
    "mistral-small-latest",
    "open-mistral-nemo",
] if m]


def _url_gemini(modelo: str) -> str:
    return f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"


def hay_ia() -> bool:
    return bool(
        os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("MISTRAL_API_KEY")
    )


def proveedores_configurados() -> list[str]:
    p = []
    if os.getenv("GROQ_API_KEY"):
        p.append("Groq")
    if os.getenv("GEMINI_API_KEY"):
        p.append("Gemini")
    if os.getenv("MISTRAL_API_KEY"):
        p.append("Mistral")
    return p


async def _pedir_groq(session, system: str, prompt: str, max_tokens: int) -> tuple[str | None, str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None, "sin GROQ_API_KEY"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ultimo = ""
    for modelo in MODELOS_GROQ:
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        try:
            async with session.post(GROQ_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data["choices"][0]["message"]["content"], modelo
                ultimo = str(data.get("error", {}).get("message", data))[:200]
                if resp.status in (400, 404):
                    continue
                break
        except Exception as e:
            ultimo = str(e)[:200]
            continue
    return None, ultimo


async def _pedir_gemini(session, system: str, prompt: str, max_tokens: int) -> tuple[str | None, str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "sin GEMINI_API_KEY"
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    ultimo = ""
    for modelo in MODELOS_GEMINI:
        try:
            async with session.post(_url_gemini(modelo), json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status == 200:
                    try:
                        return data["candidates"][0]["content"]["parts"][0]["text"], modelo
                    except (KeyError, IndexError, TypeError):
                        ultimo = "respuesta vacía"
                        continue
                ultimo = str(data.get("error", {}).get("message", data))[:200]
                if resp.status in (400, 404):
                    continue
                break
        except Exception as e:
            ultimo = str(e)[:200]
            continue
    return None, ultimo


async def _pedir_mistral(session, system: str, prompt: str, max_tokens: int) -> tuple[str | None, str]:
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        return None, "sin MISTRAL_API_KEY"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    ultimo = ""
    for modelo in MODELOS_MISTRAL:
        payload = {
            "model": modelo,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
        }
        try:
            async with session.post(MISTRAL_URL, json=payload, headers=headers) as resp:
                data = await resp.json()
                if resp.status == 200:
                    return data["choices"][0]["message"]["content"], modelo
                ultimo = str(data.get("message") or data.get("error", {}).get("message", data))[:200]
                if resp.status in (400, 404):
                    continue
                break
        except Exception as e:
            ultimo = str(e)[:200]
            continue
    return None, ultimo


async def generar(system: str, prompt: str, max_tokens: int = 400,
                  timeout_seg: int = 25) -> tuple[str | None, str]:
    """Pide texto a la IA. Devuelve (texto, info) donde `info` es el modelo usado
    si funcionó, o el mensaje de error si no. Nunca lanza excepción.

    Orden de intento: Groq → Gemini → Mistral. Si uno no tiene key configurada
    o falla (cuota agotada, error de red, etc.) se pasa automáticamente al
    siguiente, así que basta con configurar UNA de las tres para tener IA."""
    if not hay_ia():
        return None, ("No hay ninguna IA configurada. Añade GROQ_API_KEY (gratis en "
                      "https://console.groq.com/keys), GEMINI_API_KEY (gratis en "
                      "https://aistudio.google.com/apikey) o MISTRAL_API_KEY (gratis en "
                      "https://console.mistral.ai/api-keys) al archivo .env.")

    timeout = aiohttp.ClientTimeout(total=timeout_seg)
    errores = []
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for fn, nombre in ((_pedir_groq, "Groq"), (_pedir_gemini, "Gemini"), (_pedir_mistral, "Mistral")):
                texto, info = await fn(session, system, prompt, max_tokens)
                if texto:
                    return texto.strip(), f"{nombre}/{info}"
                errores.append(f"{nombre}: {info}")
    except Exception as e:
        return None, f"Error de conexión: {e}"

    return None, " | ".join(errores)
