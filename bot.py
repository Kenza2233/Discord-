import discord
from discord.ext import tasks, commands
from discord import app_commands
import aiohttp
import asyncio
import re

# -----------------------------------------------------------------------------
# GANTIKAN DENGAN INFORMASI ANDA
# -----------------------------------------------------------------------------
# Dapatkan token bot anda dari Discord Developer Portal:
# https://discord.com/developers/applications
DISCORD_BOT_TOKEN = "TOKEN_BOT_ANDA_DI_SINI"

# Dapatkan ID channel dengan mengaktifkan Developer Mode di Discord,
# kemudian klik kanan pada channel dan pilih "Copy Channel ID".
WELCOME_CHANNEL_ID = 123456789012345678  # Ganti dengan ID channel selamat datang
NOTIFICATION_CHANNEL_ID = 123456789012345678 # Ganti dengan ID channel notifikasi

# Dapatkan Place ID dari URL game Roblox:
# https://www.roblox.com/games/PLACE_ID/nama-game
ROBLOX_PLACE_ID = 123456789  # Ganti dengan Place ID game Roblox

# (Opsional) Tentukan role yang akan di-tag saat menggunakan command /check
# Klik kanan pada role dan pilih "Copy Role ID"
TAG_ROLE_ID = 123456789012345678 # Ganti dengan ID role yang akan di-tag

# Frekuensi pengecekan (dalam detik)
CHECK_INTERVAL_SECONDS = 60
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
    print('------')
    # Mulai background task untuk memeriksa status map Roblox
    check_roblox_map_status.start()

# --- Fitur akan ditambahkan di sini ---

@bot.event
async def on_member_join(member):
    """Fungsi yang dijalankan saat anggota baru bergabung dengan server."""
    # Dapatkan channel selamat datang
    welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
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
        print(f"Error: Channel selamat datang dengan ID {WELCOME_CHANNEL_ID} tidak ditemukan.")


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
    tag_role = interaction.guild.get_role(TAG_ROLE_ID)
    content = tag_role.mention if tag_role and TAG_ROLE_ID != 123456789012345678 else ""

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

# Variabel untuk menyimpan status terakhir dari map (None = belum diketahui)
map_is_public = None

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
    """Background task untuk memeriksa status map Roblox secara berkala."""
    global map_is_public

    currently_public, game_data = await get_roblox_map_details(ROBLOX_PLACE_ID)

    # Inisialisasi status awal saat bot pertama kali jalan
    if map_is_public is None:
        map_is_public = currently_public
        game_name = game_data.get('name', 'N/A') if game_data else 'N/A'
        status_str = "Publik" if currently_public else "Private"
        print(f"Status awal map Roblox '{game_name}' (ID: {ROBLOX_PLACE_ID}) adalah: {status_str}")
        return

    # Periksa jika ada perubahan dari Private ke Publik
    if currently_public and not map_is_public:
        game_name = game_data.get('name', 'N/A')
        print(f"PERUBAHAN STATUS: Map '{game_name}' sekarang PUBLIK!")
        notification_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if notification_channel:
            embed = discord.Embed(
                title="🎉 Map Roblox Sekarang Publik! 🎉",
                description=f"Map **{game_name}** sekarang sudah bisa diakses oleh semua orang!",
                color=discord.Color.blue()
            )
            game_url = f"https://www.roblox.com/games/{ROBLOX_PLACE_ID}"
            embed.add_field(name="🔗 Link Game", value=f"[Klik di sini untuk bermain]({game_url})", inline=False)
            embed.add_field(name="Pemain Aktif", value=game_data.get("playing", 0), inline=True)
            embed.add_field(name="Total Kunjungan", value=game_data.get("visits", 0), inline=True)

            await notification_channel.send(content="@everyone", embed=embed)
        else:
            print(f"Error: Channel notifikasi dengan ID {NOTIFICATION_CHANNEL_ID} tidak ditemukan.")

    # Update status terakhir
    map_is_public = currently_public


if __name__ == "__main__":
    if DISCORD_BOT_TOKEN == "TOKEN_BOT_ANDA_DI_SINI":
        print("!!! KESALAHAN: Harap ganti 'TOKEN_BOT_ANDA_DI_SINI' dengan token bot Discord Anda di file bot.py")
    elif WELCOME_CHANNEL_ID == 123456789012345678 or NOTIFICATION_CHANNEL_ID == 123456789012345678:
        print("!!! KESALAHAN: Harap ganti ID channel placeholder dengan ID channel Discord Anda yang sebenarnya di file bot.py")
    elif ROBLOX_PLACE_ID == 123456789:
        print("!!! KESALAHAN: Harap ganti ROBLOX_PLACE_ID dengan Place ID game Roblox Anda di file bot.py")
    elif TAG_ROLE_ID == 123456789012345678:
        print("!!! PERINGATAN: `TAG_ROLE_ID` belum diubah. Fitur /check akan berjalan tanpa me-mention role.")
        bot.run(DISCORD_BOT_TOKEN)
    else:
        bot.run(DISCORD_BOT_TOKEN)
