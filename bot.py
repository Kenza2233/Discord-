import discord
from discord.ext import tasks, commands
from discord import app_commands
import aiohttp
import asyncio
import re
import json
import os

# --- KONFIGURASI ---
DISCORD_BOT_TOKEN = "TOKEN_BOT_ANDA_DI_SINI"
CHECK_INTERVAL_SECONDS = 60

# --- MANAJEMEN KONFIGURASI ---
CONFIG_FILE = "config.json"
config = {}

def load_config():
    """Memuat konfigurasi dari file JSON."""
    global config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump({}, f)
        config = {}

async def save_config():
    """Menyimpan konfigurasi ke file JSON."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

load_config()
# -----------------------------------------------------------------------------

# Tentukan intents yang diperlukan bot
intents = discord.Intents.default()
intents.members = True  # Diperlukan untuk fitur selamat datang
intents.message_content = True # Diperlukan jika bot perlu membaca konten pesan

# Buat instance bot dengan prefix command (diperlukan untuk commands.Bot, tapi tidak digunakan untuk slash commands)
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    """Fungsi yang dijalankan saat bot berhasil login dan siap."""
    print(f'Bot telah login sebagai {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Berhasil menyinkronkan {len(synced)} slash command(s).")
    except Exception as e:
        print(f"Gagal menyinkronkan slash commands: {e}")

    # Inisialisasi status awal untuk semua map yang dipantau
    print("Inisialisasi status map yang dipantau...")
    for guild_id, guild_config in config.items():
        place_id = guild_config.get("roblox_place_id_to_monitor")
        if place_id and place_id not in monitored_map_states:
            is_public, _ = await get_roblox_map_details(place_id)
            monitored_map_states[place_id] = is_public
            status_str = "Publik" if is_public else "Private"
            print(f"  - Map {place_id} (Server: {guild_id}): Status awal adalah {status_str}")

    print('------')
    # Mulai background task untuk memeriksa status map Roblox
    check_roblox_map_status.start()

# --- Fitur akan ditambahkan di sini ---

# -----------------------------------------------------------------------------
# SLASH COMMAND UNTUK SETUP
# -----------------------------------------------------------------------------
setup_group = app_commands.Group(name="setup", description="Konfigurasi bot untuk server ini.", default_permissions=discord.Permissions(administrator=True))

@setup_group.command(name="set", description="Atur channel notifikasi, role ping, dan map yang dipantau.")
@app_commands.describe(
    notification_channel="Channel untuk mengirim semua notifikasi (welcome, alerts, dll).",
    ping_role="Role yang akan di-ping saat ada notifikasi status map.",
    roblox_place_id="(Opsional) Place ID dari game Roblox yang ingin dipantau secara otomatis."
)
async def setup_set(interaction: discord.Interaction, notification_channel: discord.TextChannel, ping_role: discord.Role, roblox_place_id: int = None):
    """Mengatur channel notifikasi, role untuk di-ping, dan map yang dipantau."""
    guild_id = str(interaction.guild.id)

    # Inisialisasi config untuk guild ini jika belum ada
    if guild_id not in config:
        config[guild_id] = {}

    config[guild_id]["notification_channel_id"] = notification_channel.id
    config[guild_id]["ping_role_id"] = ping_role.id
    if roblox_place_id:
        config[guild_id]["roblox_place_id_to_monitor"] = roblox_place_id

    await save_config()

    embed = discord.Embed(
        title="✅ Konfigurasi Berhasil Disimpan",
        description="Pengaturan bot untuk server ini telah diperbarui.",
        color=discord.Color.green()
    )
    embed.add_field(name="Channel Notifikasi", value=notification_channel.mention, inline=False)
    embed.add_field(name="Role untuk di-Ping", value=ping_role.mention, inline=False)
    if roblox_place_id:
        embed.add_field(name="Map yang Dipantau Otomatis", value=f"Place ID: {roblox_place_id}", inline=False)
    else:
        embed.add_field(name="Map yang Dipantau Otomatis", value="Tidak diatur. Gunakan opsi `roblox_place_id` untuk mengatur.", inline=False)


    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.tree.add_command(setup_group)


@bot.event
async def on_member_join(member):
    """Fungsi yang dijalankan saat anggota baru bergabung dengan server."""
    guild_id = str(member.guild.id)
    guild_config = config.get(guild_id)

    if guild_config and "notification_channel_id" in guild_config:
        welcome_channel_id = guild_config["notification_channel_id"]
        welcome_channel = bot.get_channel(welcome_channel_id)

        if welcome_channel:
            # Buat pesan selamat datang yang disematkan (embed)
            embed = discord.Embed(
                title=f"Selamat Datang di Server, {member.name}!",
                description=f"Senang memiliki Anda, {member.mention}! Jangan lupa baca peraturan ya.",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
            embed.set_footer(text=f"Total anggota: {member.guild.member_count}")

            await welcome_channel.send(embed=embed)
        else:
            print(f"Error: Channel notifikasi (ID: {welcome_channel_id}) untuk server {member.guild.name} tidak ditemukan.")
    else:
        print(f"Info: Server {member.guild.name} belum mengatur channel notifikasi, pesan selamat datang dilewati.")


# -----------------------------------------------------------------------------
# SLASH COMMAND UNTUK CEK MAP
# -----------------------------------------------------------------------------
@bot.tree.command(name="check", description="Periksa status map Roblox berdasarkan URL.")
@app_commands.describe(url="URL lengkap dari game Roblox yang ingin diperiksa.")
@app_commands.checks.has_permissions(administrator=True)
async def check_command(interaction: discord.Interaction, url: str):
    """Command untuk memeriksa status map Roblox secara manual."""
    # Tunda respons agar tidak timeout sambil menunggu API
    await interaction.response.defer()

    # Ekstrak Place ID dari URL menggunakan regex
    match = re.search(r"roblox\.com/games/(\d+)", url)
    if not match:
        await interaction.followup.send("URL tidak valid. Harap berikan URL game Roblox yang benar.", ephemeral=True)
        return

    place_id = int(match.group(1))

    is_public, game_data = await get_roblox_map_details(place_id)

    # Siapkan pesan notifikasi
    guild_id = str(interaction.guild.id)
    guild_config = config.get(guild_id, {})
    ping_role_id = guild_config.get("ping_role_id")

    content = ""
    if ping_role_id:
        role = interaction.guild.get_role(ping_role_id)
        if role:
            content = role.mention

    if game_data: # Jika game ditemukan (baik publik maupun private, tapi API kita hanya mengembalikan data jika publik)
        game_name = game_data.get('name', 'N/A')
        embed = discord.Embed(
            title=f"Status Map: {game_name}",
            color=discord.Color.green() if is_public else discord.Color.red()
        )
        status_text = "✅ PUBLIK" if is_public else "❌ PRIVATE"
        embed.description = f"Map ini saat ini **{status_text}**."

        game_url = f"https://www.roblox.com/games/{place_id}"
        embed.add_field(name="🔗 Link Game", value=f"[Klik di sini untuk bermain]({game_url})", inline=False)
        embed.add_field(name="Pemain Aktif", value=game_data.get("playing", "N/A"), inline=True)
        embed.add_field(name="Total Kunjungan", value=game_data.get("visits", "N/A"), inline=True)
        embed.set_footer(text=f"Pemeriksaan diminta oleh: {interaction.user.display_name}")
    else: # Jika game tidak ditemukan atau private
        embed = discord.Embed(
            title="Status Map Tidak Diketahui",
            description=f"Tidak dapat mengambil detail untuk game dengan URL yang diberikan. Kemungkinan map tersebut **PRIVATE** atau URL tidak valid.",
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"Pemeriksaan diminta oleh: {interaction.user.display_name}")

    await interaction.followup.send(content=content, embed=embed)

@check_command.error
async def check_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("Maaf, Anda tidak memiliki izin 'Administrator' untuk menggunakan command ini.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Terjadi kesalahan: {error}", ephemeral=True)


# -----------------------------------------------------------------------------
# FITUR PEMERIKSA STATUS MAP ROBLOX
# -----------------------------------------------------------------------------

# Variabel untuk menyimpan status terakhir dari semua map yang dipantau
# Format: {place_id: is_public}
monitored_map_states = {}

async def get_roblox_map_details(place_id: int):
    """
    Mengambil detail map dari Roblox API berdasarkan Place ID.
    Mengembalikan tuple: (is_public, game_data)
    """
    universe_id = None
    try:
        async with aiohttp.ClientSession() as session:
            # 1. Dapatkan Universe ID dari Place ID
            universe_api_url = f"https://apis.roblox.com/universes/v1/places/{place_id}/universe"
            async with session.get(universe_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    universe_id = data.get("universeId")
                else:
                    print(f"Error saat mengambil Universe ID untuk Place ID {place_id}: Status {response.status}")
                    return False, None

            if not universe_id:
                print(f"Tidak dapat menemukan Universe ID untuk Place ID {place_id}.")
                return False, None

            # 2. Dapatkan detail game dari Universe ID
            games_api_url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
            async with session.get(games_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        return True, data["data"][0] # (is_public, game_data)
                    else:
                        return False, None # Game private atau tidak ditemukan
                else:
                    print(f"Error saat mengambil detail game untuk Universe ID {universe_id}: Status {response.status}")
                    return False, None

    except aiohttp.ClientError as e:
        print(f"Terjadi kesalahan jaringan saat memeriksa Place ID {place_id}: {e}")
        return False, None
    except Exception as e:
        print(f"Terjadi kesalahan tak terduga saat memeriksa Place ID {place_id}: {e}")
        return False, None

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def check_roblox_map_status():
    """Background task untuk memeriksa status semua map Roblox yang dipantau."""
    # Kumpulkan semua place ID unik yang perlu diperiksa
    unique_place_ids = set(
        guild_config.get("roblox_place_id_to_monitor")
        for guild_config in config.values()
        if guild_config.get("roblox_place_id_to_monitor")
    )

    for place_id in unique_place_ids:
        currently_public, game_data = await get_roblox_map_details(place_id)

        # Jika place_id belum pernah dicek, inisialisasi statusnya
        if place_id not in monitored_map_states:
            monitored_map_states[place_id] = currently_public
            game_name = game_data.get('name', 'N/A') if game_data else 'N/A'
            status_str = "Publik" if currently_public else "Private"
            print(f"Status awal map '{game_name}' (ID: {place_id}) adalah: {status_str}")
            continue

        last_known_status = monitored_map_states[place_id]

        # Periksa jika ada perubahan dari Private ke Publik
        if currently_public and not last_known_status:
            game_name = game_data.get('name', 'N/A')
            print(f"PERUBAHAN STATUS: Map '{game_name}' (ID: {place_id}) sekarang PUBLIK!")

            # Kirim notifikasi ke semua server yang memantau place_id ini
            for guild_id, guild_config in config.items():
                if guild_config.get("roblox_place_id_to_monitor") == place_id:
                    channel_id = guild_config.get("notification_channel_id")
                    channel = bot.get_channel(channel_id) if channel_id else None

                    if channel:
                        embed = discord.Embed(
                            title="🎉 Map Roblox Sekarang Publik! 🎉",
                            description=f"Map **{game_name}** yang Anda pantau sekarang sudah bisa diakses oleh semua orang!",
                            color=discord.Color.blue()
                        )
                        game_url = f"https://www.roblox.com/games/{place_id}"
                        embed.add_field(name="🔗 Link Game", value=f"[Klik di sini untuk bermain]({game_url})", inline=False)
                        embed.add_field(name="Pemain Aktif", value=game_data.get("playing", 0), inline=True)
                        embed.add_field(name="Total Kunjungan", value=game_data.get("visits", 0), inline=True)

                        ping_role_id = guild_config.get("ping_role_id")
                        content = ""
                        if ping_role_id:
                            role = channel.guild.get_role(ping_role_id)
                            if role:
                                content = role.mention

                        await channel.send(content=content, embed=embed)
                    else:
                        print(f"Error: Channel notifikasi untuk server ID {guild_id} tidak ditemukan atau tidak diatur.")

        # Update status terakhir untuk place_id ini
        monitored_map_states[place_id] = currently_public


if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == "TOKEN_BOT_ANDA_DI_SINI":
        print("!!! KESALAHAN: Harap ganti 'TOKEN_BOT_ANDA_DI_SINI' dengan token bot Discord Anda di file bot.py")
    else:
        bot.run(DISCORD_BOT_TOKEN)
