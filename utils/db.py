"""
utils/db.py — Capa de persistencia real (SQLite por defecto, MySQL opcional).

Mantiene EXACTAMENTE la misma API pública que la versión vieja basada en JSON
(get/set/delete/all/update), así que ningún cog necesita cambiar una sola línea.

Configuración (variables de entorno):
    DB_BACKEND   = "sqlite" (default) | "mysql"

    # Solo si DB_BACKEND=sqlite (default, no necesitas configurar nada)
    DB_PATH      = "data/rp.db"   (default)

    # Solo si DB_BACKEND=mysql
    MYSQL_HOST     = "localhost"
    MYSQL_PORT     = 3306
    MYSQL_USER     = "root"
    MYSQL_PASSWORD = ""
    MYSQL_DB       = "venezuelarp"

Cada "tabla" (banco, personajes, casas, npcs, etc.) es una tabla SQL real con
2 columnas: `id` (clave, TEXT) y `data` (JSON serializado como texto). Esto nos
da persistencia real y la posibilidad de escalar a MySQL sin tocar los cogs.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

BACKEND = os.getenv("DB_BACKEND", "sqlite").strip().lower()
_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_locks: dict[str, asyncio.Lock] = {}
_ready_tables: set[str] = set()
_init_lock = asyncio.Lock()


def _lock(table: str) -> asyncio.Lock:
    if table not in _locks:
        _locks[table] = asyncio.Lock()
    return _locks[table]


def _safe_table(table: str) -> str:
    """Evita inyección SQL en nombres de tabla (no se pueden parametrizar)."""
    if not _TABLE_NAME_RE.match(table):
        raise ValueError(f"Nombre de tabla inválido: {table!r}")
    return f"t_{table}"


# ══════════════════════════════════════════════════════════════════════════
# Backend: SQLite (default)
# ══════════════════════════════════════════════════════════════════════════
class _SQLiteBackend:
    def __init__(self):
        import aiosqlite  # import perezoso: no exigimos la dependencia si se usa MySQL
        self._aiosqlite = aiosqlite
        self._path = os.getenv("DB_PATH", str(DATA_DIR / "rp.db"))
        self._conn: Optional["aiosqlite.Connection"] = None

    async def _get_conn(self):
        if self._conn is None:
            self._conn = await self._aiosqlite.connect(self._path)
            await self._conn.execute("PRAGMA journal_mode=WAL;")
            await self._conn.commit()
        return self._conn

    async def ensure_table(self, table: str):
        conn = await self._get_conn()
        real = _safe_table(table)
        await conn.execute(
            f"CREATE TABLE IF NOT EXISTS {real} ("
            f"id TEXT PRIMARY KEY, data TEXT NOT NULL)"
        )
        await conn.commit()

    async def get(self, table: str, key: str) -> Optional[Any]:
        conn = await self._get_conn()
        real = _safe_table(table)
        async with conn.execute(f"SELECT data FROM {real} WHERE id = ?", (key,)) as cur:
            row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def set(self, table: str, key: str, value: Any):
        conn = await self._get_conn()
        real = _safe_table(table)
        payload = json.dumps(value, ensure_ascii=False)
        await conn.execute(
            f"INSERT INTO {real} (id, data) VALUES (?, ?) "
            f"ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (key, payload),
        )
        await conn.commit()

    async def delete(self, table: str, key: str):
        conn = await self._get_conn()
        real = _safe_table(table)
        await conn.execute(f"DELETE FROM {real} WHERE id = ?", (key,))
        await conn.commit()

    async def all(self, table: str) -> dict:
        conn = await self._get_conn()
        real = _safe_table(table)
        async with conn.execute(f"SELECT id, data FROM {real}") as cur:
            rows = await cur.fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    async def close(self):
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


# ══════════════════════════════════════════════════════════════════════════
# Backend: MySQL (opcional — solo se importa aiomysql si se usa este backend)
# ══════════════════════════════════════════════════════════════════════════
class _MySQLBackend:
    def __init__(self):
        try:
            import aiomysql  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "DB_BACKEND=mysql pero falta el paquete 'aiomysql'. "
                "Instálalo con: pip install aiomysql"
            ) from e
        self._aiomysql = aiomysql
        self._pool = None
        self._cfg = dict(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            db=os.getenv("MYSQL_DB", "venezuelarp"),
            autocommit=True,
        )

    async def _get_pool(self):
        if self._pool is None:
            self._pool = await self._aiomysql.create_pool(**self._cfg, minsize=1, maxsize=10)
        return self._pool

    async def ensure_table(self, table: str):
        pool = await self._get_pool()
        real = _safe_table(table)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"CREATE TABLE IF NOT EXISTS `{real}` ("
                    f"id VARCHAR(191) PRIMARY KEY, data LONGTEXT NOT NULL)"
                    f" ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                )

    async def get(self, table: str, key: str) -> Optional[Any]:
        pool = await self._get_pool()
        real = _safe_table(table)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT data FROM `{real}` WHERE id = %s", (key,))
                row = await cur.fetchone()
        return json.loads(row[0]) if row else None

    async def set(self, table: str, key: str, value: Any):
        pool = await self._get_pool()
        real = _safe_table(table)
        payload = json.dumps(value, ensure_ascii=False)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"INSERT INTO `{real}` (id, data) VALUES (%s, %s) "
                    f"ON DUPLICATE KEY UPDATE data = VALUES(data)",
                    (key, payload),
                )

    async def delete(self, table: str, key: str):
        pool = await self._get_pool()
        real = _safe_table(table)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"DELETE FROM `{real}` WHERE id = %s", (key,))

    async def all(self, table: str) -> dict:
        pool = await self._get_pool()
        real = _safe_table(table)
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(f"SELECT id, data FROM `{real}`")
                rows = await cur.fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    async def close(self):
        if self._pool is not None:
            self._pool.close()
            await self._pool.wait_closed()
            self._pool = None


_backend = _SQLiteBackend() if BACKEND == "sqlite" else _MySQLBackend()


async def _ensure(table: str):
    if table in _ready_tables:
        return
    async with _init_lock:
        if table not in _ready_tables:
            await _backend.ensure_table(table)
            _ready_tables.add(table)


# ══════════════════════════════════════════════════════════════════════════
# API pública (idéntica a la versión JSON anterior)
# ══════════════════════════════════════════════════════════════════════════
async def get(table: str, key: str) -> Optional[Any]:
    await _ensure(table)
    async with _lock(table):
        return await _backend.get(table, str(key))


async def set(table: str, key: str, value: Any):
    await _ensure(table)
    async with _lock(table):
        await _backend.set(table, str(key), value)


async def delete(table: str, key: str):
    await _ensure(table)
    async with _lock(table):
        await _backend.delete(table, str(key))


async def all(table: str) -> dict:
    await _ensure(table)
    async with _lock(table):
        return await _backend.all(table)


async def update(table: str, key: str, partial: dict):
    await _ensure(table)
    async with _lock(table):
        k = str(key)
        current = await _backend.get(table, k) or {}
        current.update(partial)
        await _backend.set(table, k, current)


async def close():
    """Llamar al apagar el bot (opcional, cierra la conexión/pool limpiamente)."""
    await _backend.close()


def backend_name() -> str:
    return BACKEND
