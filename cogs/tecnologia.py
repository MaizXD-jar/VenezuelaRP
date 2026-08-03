"""
cogs/tecnologia.py — Internet, PCs, VPN, redes sociales bloqueadas, hackeo, streaming.
En Venezuela Twitter/X y TikTok requieren VPN. Hay apagones que cortan internet.
"""
import discord
from discord.ext import commands, tasks
import random
import asyncio
import time
from utils import db

# ── PLANES DE INTERNET ────────────────────────────────────────────────────────
PLANES_INTERNET = {
    "cantv_basico":   {"display": "CANTV Básico",    "precio_mes": 5.0,   "velocidad": "1 Mbps",  "cortes": 0.35},
    "cantv_medio":    {"display": "CANTV Medio",     "precio_mes": 12.0,  "velocidad": "10 Mbps", "cortes": 0.25},
    "inter_hogar":    {"display": "Inter Hogar",     "precio_mes": 25.0,  "velocidad": "50 Mbps", "cortes": 0.10},
    "movilnet_datos": {"display": "Movilnet Datos",  "precio_mes": 8.0,   "velocidad": "4G",       "cortes": 0.20},
    "digitel_4g":     {"display": "Digitel 4G",      "precio_mes": 15.0,  "velocidad": "4G+",      "cortes": 0.08},
}

# ── VPNs ──────────────────────────────────────────────────────────────────────
VPNS = {
    "vpn_gratis":   {"display": "VPN Gratis",         "precio": 0,     "duracion_dias": 3,   "fiabilidad": 0.60},
    "vpn_basica":   {"display": "VPN Básica",         "precio": 2.0,   "duracion_dias": 30,  "fiabilidad": 0.80},
    "vpn_premium":  {"display": "VPN Premium",        "precio": 8.0,   "duracion_dias": 30,  "fiabilidad": 0.97},
    "vpn_elite":    {"display": "VPN Élite (ilegal)", "precio": 20.0,  "duracion_dias": 90,  "fiabilidad": 0.99},
}

# ── PCs ───────────────────────────────────────────────────────────────────────
COMPUTADORAS = {
    "pc_basica":    {"display": "PC Básica",         "precio": 200,  "ram": "4GB",  "hack_bonus": 1.0, "stream_bonus": 0.5},
    "pc_media":     {"display": "PC Mediana",        "precio": 600,  "ram": "8GB",  "hack_bonus": 1.5, "stream_bonus": 1.0},
    "pc_gamer":     {"display": "PC Gamer",          "precio": 1500, "ram": "16GB", "hack_bonus": 2.0, "stream_bonus": 2.0},
    "servidor":     {"display": "Servidor Linux",    "precio": 3000, "ram": "32GB", "hack_bonus": 3.5, "stream_bonus": 1.5},
    "laptop_vieja": {"display": "Laptop Vieja",      "precio": 80,   "ram": "2GB",  "hack_bonus": 0.7, "stream_bonus": 0.3},
}

# Redes bloqueadas en Venezuela (requieren VPN)
REDES_BLOQUEADAS = ["twitter", "x", "tiktok", "instagram", "youtube"]

# ── IDs canales de noticias ───────────────────────────────────────────────────
CH_NOTICIAS_VZ1  = 1382156099473379458
CH_NOTICIAS_VZ2  = 1382156210576425040
CH_NOTICIAS_INT  = 1382156276016087110


class Tecnologia(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cobrar_internet.start()
        self.apagones_aleatorios.start()

    def start_tasks(self):
        if not self.cobrar_internet.is_running():
            self.cobrar_internet.start()
        if not self.apagones_aleatorios.is_running():
            self.apagones_aleatorios.start()

    # ── TASK: cobrar internet mensual ─────────────────────────────────────────
    @tasks.loop(hours=168)  # cada 7 días (simula mes acelerado)
    async def cobrar_internet(self):
        personajes = await db.all("personajes")
        for uid, datos in personajes.items():
            internet = datos.get("internet")
            if not internet:
                continue
            plan = PLANES_INTERNET.get(internet.get("plan",""))
            if not plan:
                continue
            dinero = datos.get("dinero", 0)
            # Si es menor, los padres pagan
            if datos.get("edad", 18) < 18:
                continue
            costo = plan["precio_mes"] * 0.25  # por semana
            if dinero < costo:
                # Sin dinero: cortar internet
                await db.update("personajes", uid, {"internet": None})
            else:
                await db.update("personajes", uid, {"dinero": round(dinero - costo, 2)})

    # ── TASK: apagones aleatorios ─────────────────────────────────────────────
    @tasks.loop(hours=4)
    async def apagones_aleatorios(self):
        """Simula apagones en sectores de alto peligro/pobreza."""
        from utils.mapa import SECTORES
        for guild in self.bot.guilds:
            for sector_key, sec_info in SECTORES.items():
                peligro = sec_info.get("peligro", 1)
                # Solo en sectores con peligro >= 3
                if peligro < 3:
                    continue
                prob = peligro * 0.04  # max ~20% chance
                if random.random() > prob:
                    continue
                duracion = random.randint(30, 240)  # 30 min a 4h
                # Notificar en un canal del sector
                canales_sec = list(sec_info.get("canales", {}).keys())
                if not canales_sec:
                    continue
                nombre_canal = canales_sec[0]
                canal = discord.utils.get(guild.text_channels, name=nombre_canal)
                if not canal:
                    continue
                embed = discord.Embed(
                    title="⚡ APAGÓN",
                    description=f"¡Se fue la luz en **{sec_info.get('display', sector_key)}**!\nDuración estimada: {duracion} minutos.\nInternet sin funcionar en la zona.",
                    color=0x1a1a1a
                )
                embed.set_footer(text="La electricidad es un lujo en Venezuela.")
                await canal.send(embed=embed)

                # Marcar apagón en DB
                apagones = await db.get("eventos", "apagones") or {}
                apagones[sector_key] = {"hasta_ts": time.time() + duracion * 60}
                await db.set("eventos", "apagones", apagones)

    # ── /comprar_internet ─────────────────────────────────────────────────────
    @commands.command(name="contratar_internet")
    async def contratar_internet(self, ctx, plan: str):
        """Contrata un plan de internet. /contratar_internet <plan>"""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        plan = plan.lower()
        if plan not in PLANES_INTERNET:
            planes_txt = ", ".join(PLANES_INTERNET.keys())
            return await ctx.send(f"❌ Plan no válido. Disponibles: `{planes_txt}`")

        info = PLANES_INTERNET[plan]
        dinero = datos.get("dinero", 0)
        costo = info["precio_mes"]

        if datos.get("edad", 18) < 18:
            await ctx.send("✅ Como eres menor de edad, tus padres pagan el internet.")
        elif dinero < costo:
            return await ctx.send(f"❌ Necesitas ${costo:.2f} para el primer mes. Tienes ${dinero:.2f}.")
        else:
            await db.update("personajes", str(ctx.author.id), {
                "dinero": round(dinero - costo, 2)
            })

        await db.update("personajes", str(ctx.author.id), {
            "internet": {"plan": plan, "activo": True, "desde_ts": time.time()}
        })

        embed = discord.Embed(title="🌐 Internet contratado", color=0x00BFFF)
        embed.add_field(name="Plan", value=info["display"])
        embed.add_field(name="Velocidad", value=info["velocidad"])
        embed.add_field(name="Costo", value=f"${costo:.2f}/mes")
        await ctx.send(embed=embed)

    # ── /planes_internet ──────────────────────────────────────────────────────
    @commands.command(name="planes_internet")
    async def planes_internet(self, ctx):
        embed = discord.Embed(title="🌐 Planes de Internet Venezuela", color=0x00BFFF)
        for key, info in PLANES_INTERNET.items():
            embed.add_field(
                name=f"`{key}` — {info['display']}",
                value=f"💰 ${info['precio_mes']:.2f}/mes | 📶 {info['velocidad']} | Cortes: {int(info['cortes']*100)}%",
                inline=False
            )
        await ctx.send(embed=embed)

    # ── /vpn ──────────────────────────────────────────────────────────────────
    @commands.command(name="vpn")
    async def comprar_vpn(self, ctx, tipo: str = None):
        """Compra/activa una VPN. /vpn <tipo>"""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        if not datos.get("internet", {}).get("activo"):
            return await ctx.send("❌ Necesitas internet para usar VPN.")

        if tipo is None:
            embed = discord.Embed(title="🔒 VPNs Disponibles", color=0x9B59B6)
            for key, info in VPNS.items():
                precio_txt = "Gratis" if info["precio"] == 0 else f"${info['precio']:.2f}"
                embed.add_field(
                    name=f"`{key}` — {info['display']}",
                    value=f"💰 {precio_txt} | ⏱️ {info['duracion_dias']} días | 📶 Fiabilidad: {int(info['fiabilidad']*100)}%",
                    inline=False
                )
            embed.set_footer(text="Con VPN puedes acceder a Twitter, TikTok y redes bloqueadas.")
            return await ctx.send(embed=embed)

        tipo = tipo.lower()
        if tipo not in VPNS:
            return await ctx.send(f"❌ VPN no válida. Usa `/vpn` para ver opciones.")

        info = VPNS[tipo]
        dinero = datos.get("dinero", 0)
        if dinero < info["precio"]:
            return await ctx.send(f"❌ Necesitas ${info['precio']:.2f}. Tienes ${dinero:.2f}.")

        await db.update("personajes", str(ctx.author.id), {
            "vpn": {
                "tipo": tipo,
                "activa": True,
                "vence_ts": time.time() + info["duracion_dias"] * 86400,
                "fiabilidad": info["fiabilidad"],
            },
            "dinero": round(dinero - info["precio"], 2)
        })

        embed = discord.Embed(title=f"🔒 VPN activada: {info['display']}", color=0x9B59B6)
        embed.add_field(name="Duración", value=f"{info['duracion_dias']} días")
        embed.add_field(name="Fiabilidad", value=f"{int(info['fiabilidad']*100)}%")
        embed.add_field(name="Redes desbloqueadas", value="Twitter/X, TikTok, Instagram, YouTube, etc.")
        await ctx.send(embed=embed)

    # ── /comprar_pc ───────────────────────────────────────────────────────────
    @commands.command(name="comprar_pc")
    async def comprar_pc(self, ctx, tipo: str = None):
        """Compra una computadora. /comprar_pc <tipo>"""
        if tipo is None:
            embed = discord.Embed(title="🖥️ Computadoras Disponibles", color=0x3498DB)
            for key, info in COMPUTADORAS.items():
                embed.add_field(
                    name=f"`{key}` — {info['display']}",
                    value=f"💰 ${info['precio']:,} | RAM: {info['ram']} | Hack: x{info['hack_bonus']} | Stream: x{info['stream_bonus']}",
                    inline=False
                )
            return await ctx.send(embed=embed)

        tipo = tipo.lower()
        if tipo not in COMPUTADORAS:
            return await ctx.send(f"❌ PC no válida. Usa `/comprar_pc` para ver opciones.")

        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        info = COMPUTADORAS[tipo]
        dinero = datos.get("dinero", 0)
        if dinero < info["precio"]:
            return await ctx.send(f"❌ Necesitas ${info['precio']:,}. Tienes ${dinero:.2f}.")

        inventario = datos.get("inventario", {})
        inventario[tipo] = inventario.get(tipo, 0) + 1

        await db.update("personajes", str(ctx.author.id), {
            "inventario": inventario,
            "pc": tipo,
            "dinero": round(dinero - info["precio"], 2)
        })
        await ctx.send(f"🖥️ Compraste **{info['display']}** por ${info['precio']:,}. ¡Listo para hackear!")

    # ── /twitter ──────────────────────────────────────────────────────────────
    @commands.command(name="twitter", aliases=["x"])
    async def twitter(self, ctx, *, tweet: str = None):
        """Publica en Twitter/X. Requiere VPN en Venezuela."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        if not datos.get("internet", {}).get("activo"):
            return await ctx.send("❌ Sin internet. Contrata uno con `/contratar_internet`.")

        vpn = datos.get("vpn", {})
        vpn_activa = vpn.get("activa") and vpn.get("vence_ts", 0) > time.time()

        if not vpn_activa:
            return await ctx.send(
                "🚫 **Twitter/X está bloqueado en Venezuela.**\n"
                "Necesitas una VPN para acceder. Usa `/vpn` para ver opciones."
            )

        # Verificar si la VPN falla (por fiabilidad)
        fiabilidad = vpn.get("fiabilidad", 0.8)
        if random.random() > fiabilidad:
            return await ctx.send("❌ Tu VPN falló. Intenta de nuevo o actualiza a una mejor.")

        if tweet is None:
            return await ctx.send("❌ Uso: `/twitter <tu tweet>`")

        nombre = datos.get("nombre", ctx.author.display_name)
        embed = discord.Embed(
            description=f"🐦 **{nombre}** tweetea:\n\n{tweet}",
            color=0x1DA1F2
        )
        embed.set_author(name=f"@{nombre.lower().replace(' ','_')}", icon_url=ctx.author.display_avatar.url)
        embed.set_footer(text="Twitter/X • Accedido via VPN 🔒")
        await ctx.send(embed=embed)

        # Guardar en historial
        tweets = datos.get("tweets", [])
        tweets.append({"texto": tweet[:280], "ts": time.time()})
        tweets = tweets[-20:]
        await db.update("personajes", str(ctx.author.id), {"tweets": tweets})

    # ── /tiktok ───────────────────────────────────────────────────────────────
    @commands.command(name="tiktok")
    async def tiktok(self, ctx, *, descripcion: str = None):
        """Publica en TikTok. Requiere VPN."""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        if not datos.get("internet", {}).get("activo"):
            return await ctx.send("❌ Sin internet.")
        vpn = datos.get("vpn", {})
        if not (vpn.get("activa") and vpn.get("vence_ts", 0) > time.time()):
            return await ctx.send("🚫 **TikTok está bloqueado en Venezuela.** Necesitas VPN.")
        if not descripcion:
            return await ctx.send("❌ Uso: `/tiktok <descripción del video>`")
        nombre = datos.get("nombre", ctx.author.display_name)
        views = random.randint(0, 50000)
        likes = int(views * random.uniform(0.03, 0.15))
        embed = discord.Embed(description=f"🎵 **{nombre}** publica en TikTok:\n_{descripcion}_", color=0x010101)
        embed.add_field(name="👀 Views", value=f"{views:,}")
        embed.add_field(name="❤️ Likes", value=f"{likes:,}")
        embed.set_footer(text="TikTok • Accedido via VPN 🔒")
        await ctx.send(embed=embed)

    # ── /hackear ──────────────────────────────────────────────────────────────
    @commands.command(name="hackear")
    async def hackear(self, ctx, objetivo: discord.Member, tipo: str = "cuenta"):
        """Hackea a alguien. Tipos: cuenta, banco, ubicacion. Necesitas PC + internet."""
        datos_h = await db.get("personajes", str(ctx.author.id))
        datos_v = await db.get("personajes", str(objetivo.id))
        if not datos_h:
            return await ctx.send("❌ Sin personaje.")
        if not datos_v:
            return await ctx.send("❌ El objetivo no tiene personaje.")

        # Verificar PC e internet
        if not datos_h.get("pc"):
            return await ctx.send("❌ Necesitas una PC. Usa `/comprar_pc`.")
        if not datos_h.get("internet", {}).get("activo"):
            return await ctx.send("❌ Sin internet.")

        pc_tipo = datos_h.get("pc", "laptop_vieja")
        pc_info = COMPUTADORAS.get(pc_tipo, {"hack_bonus": 1.0})
        hack_bonus = pc_info.get("hack_bonus", 1.0)

        # Bonus por trabajo
        trabajo = datos_h.get("trabajo_actual", "")
        from cogs.trabajos import TRABAJOS
        job = TRABAJOS.get(trabajo, {})
        if job.get("bonus_hack"):
            hack_bonus *= 1.5

        # Stats del hacker
        inteligencia = datos_h.get("stats", {}).get("inteligencia", 5)
        tecnica = datos_h.get("stats", {}).get("tecnica", 3)
        prob_base = (inteligencia + tecnica) / 40 * hack_bonus

        tipos_validos = ["cuenta", "banco", "ubicacion", "telefono"]
        if tipo not in tipos_validos:
            return await ctx.send(f"❌ Tipo inválido. Usa: {', '.join(tipos_validos)}")

        await ctx.send(f"💻 Intentando hackear **{datos_v['nombre']}**... (`{tipo}`)")
        await asyncio.sleep(2)

        if random.random() > min(0.75, prob_base):
            await ctx.send("❌ Hackeo fallido. Firewall bloqueó el intento.")
            # Notificar a víctima
            try:
                await objetivo.send(f"⚠️ Alguien intentó hackear tu **{tipo}**. IP detectada (parcialmente).")
            except:
                pass
            return

        # Éxito
        nombre_v = datos_v.get("nombre", "?")
        if tipo == "banco":
            from cogs.banco import BANCOS
            cuenta_v = await db.get("cuentas_banco", str(objetivo.id))
            if not cuenta_v or cuenta_v.get("saldo", 0) <= 0:
                return await ctx.send("✅ Hackeo exitoso pero la víctima no tiene saldo.")
            robado = round(cuenta_v["saldo"] * random.uniform(0.10, 0.30), 2)
            cuenta_v["saldo"] = round(cuenta_v["saldo"] - robado, 2)
            await db.set("cuentas_banco", str(objetivo.id), cuenta_v)
            cuenta_h = await db.get("cuentas_banco", str(ctx.author.id)) or {"saldo": 0}
            cuenta_h["saldo"] = round(cuenta_h.get("saldo", 0) + robado, 2)
            await db.set("cuentas_banco", str(ctx.author.id), cuenta_h)
            await ctx.send(f"💻 ✅ Hackeaste el banco de **{nombre_v}**. Robaste ${robado:.2f}.")

        elif tipo == "ubicacion":
            ubicacion = datos_v.get("ubicacion", "desconocida")
            canal = datos_v.get("canal_actual", "?")
            await ctx.send(f"💻 ✅ Ubicación de **{nombre_v}**: `{canal}` en `{ubicacion}`.")

        elif tipo == "telefono":
            tel = datos_v.get("telefono", "desconocido")
            await ctx.send(f"💻 ✅ Teléfono de **{nombre_v}**: `{tel}`.")

        elif tipo == "cuenta":
            # Robamos info básica (dinero, inventario)
            dinero_v = datos_v.get("dinero", 0)
            inv_v = list(datos_v.get("inventario", {}).keys())
            await ctx.send(
                f"💻 ✅ Info de **{nombre_v}**:\n"
                f"💵 Dinero en efectivo: ${dinero_v:.2f}\n"
                f"🎒 Inventario: {', '.join(inv_v[:10]) if inv_v else 'vacío'}"
            )

        try:
            await objetivo.send(f"🚨 ¡Tu **{tipo}** fue hackeado/a!")
        except:
            pass

    # ── /mi_internet ──────────────────────────────────────────────────────────
    @commands.command(name="mi_internet")
    async def mi_internet(self, ctx):
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")
        internet = datos.get("internet")
        vpn = datos.get("vpn")
        pc = datos.get("pc")
        embed = discord.Embed(title="🖥️ Mi Tecnología", color=0x3498DB)
        if internet:
            plan = PLANES_INTERNET.get(internet.get("plan",""), {})
            embed.add_field(name="🌐 Internet", value=f"{plan.get('display','?')} — {plan.get('velocidad','?')}")
        else:
            embed.add_field(name="🌐 Internet", value="Sin internet. Usa `/contratar_internet`.")
        if vpn:
            vence = vpn.get("vence_ts", 0)
            restante = max(0, int((vence - time.time()) / 3600))
            estado = f"✅ Activa ({restante}h restantes)" if vence > time.time() else "❌ Vencida"
            embed.add_field(name="🔒 VPN", value=f"{vpn.get('tipo','?')} — {estado}")
        else:
            embed.add_field(name="🔒 VPN", value="Sin VPN. Usa `/vpn`.")
        if pc:
            pc_info = COMPUTADORAS.get(pc, {})
            embed.add_field(name="🖥️ PC", value=pc_info.get("display", pc))
        else:
            embed.add_field(name="🖥️ PC", value="Sin PC. Usa `/comprar_pc`.")
        await ctx.send(embed=embed)

    # ── /noticias ─────────────────────────────────────────────────────────────
    @commands.command(name="noticias")
    async def ver_noticias(self, ctx, tipo: str = "venezuela"):
        """Ve las noticias. Requiere TV + internet. /noticias [venezuela|internacional]"""
        datos = await db.get("personajes", str(ctx.author.id))
        if not datos:
            return await ctx.send("❌ Sin personaje.")

        inv = datos.get("inventario", {})
        tiene_tv = "television" in inv or "tv" in inv
        tiene_internet = datos.get("internet", {}).get("activo")

        if not tiene_tv and not tiene_internet:
            return await ctx.send("❌ Necesitas una **televisión** o **internet** para ver noticias.")

        tipo = tipo.lower()
        if tipo in ("venezuela", "vz", "nacional"):
            ch = ctx.guild.get_channel(CH_NOTICIAS_VZ1) or ctx.guild.get_channel(CH_NOTICIAS_VZ2)
            canal_nombre = "Canal venezolano"
        else:
            ch = ctx.guild.get_channel(CH_NOTICIAS_INT)
            canal_nombre = "Canal internacional"

        if ch:
            await ctx.send(f"📺 Sintonizando **{canal_nombre}**: {ch.mention}")
        else:
            await ctx.send(f"📺 El canal de noticias no está disponible en este momento.")

    # ── /apagar_luz (admin) ───────────────────────────────────────────────────
    @commands.command(name="apagon")
    async def apagon_manual(self, ctx, sector: str, duracion: int = 60):
        """[ADMIN] Genera apagón manual en un sector."""
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("❌ Solo admins.")
        from utils.mapa import SECTORES
        if sector not in SECTORES:
            return await ctx.send(f"❌ Sector `{sector}` no encontrado.")
        sec = SECTORES[sector]
        apagones = await db.get("eventos", "apagones") or {}
        apagones[sector] = {"hasta_ts": time.time() + duracion * 60}
        await db.set("eventos", "apagones", apagones)
        canales = list(sec.get("canales", {}).keys())
        for nombre_canal in canales[:3]:
            canal = discord.utils.get(ctx.guild.text_channels, name=nombre_canal)
            if canal:
                embed = discord.Embed(
                    title="⚡ APAGÓN PROGRAMADO",
                    description=f"La electricidad en **{sec.get('display', sector)}** se ha ido.\nDuración: {duracion} minutos.",
                    color=0x1a1a1a
                )
                await canal.send(embed=embed)
                break
        await ctx.send(f"⚡ Apagón en `{sector}` por {duracion} min.")


async def setup(bot):
    await bot.add_cog(Tecnologia(bot))