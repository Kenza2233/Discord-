import discord
from discord.ext import tasks
import aiohttp
import asyncio

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

# Frekuensi pengecekan (dalam detik)
CHECK_INTERVAL_SECONDS = 60
# -----------------------------------------------------------------------------

# Tentukan intents yang diperlukan bot
intents = discord.Intents.default()
intents.members = True  # Diperlukan untuk fitur selamat datang
intents.message_content = True # Diperlukan jika bot perlu membaca konten pesan

# Buat instance bot
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    """Fungsi yang dijalankan saat bot berhasil login dan siap."""
    print(f'Bot telah login sebagai {bot.user}')
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
# FITUR PEMERIKSA STATUS MAP ROBLOX
# -----------------------------------------------------------------------------

# Variabel untuk menyimpan status terakhir dari map (None = belum diketahui)
map_is_public = None

@tasks.loop(seconds=CHECK_INTERVAL_SECONDS)
async def check_roblox_map_status():
    """Background task untuk memeriksa status map Roblox secara berkala."""
    global map_is_public

    universe_id = None
    currently_public = False
    game_data = {}

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Dapatkan Universe ID dari Place ID
            universe_api_url = f"https://apis.roblox.com/universes/v1/places/{ROBLOX_PLACE_ID}/universe"
            async with session.get(universe_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    universe_id = data.get("universeId")
                else:
                    print(f"Error saat mengambil Universe ID: Status {response.status}")
                    return

            if not universe_id:
                print("Tidak dapat menemukan Universe ID untuk Place ID yang diberikan.")
                return

            # 2. Dapatkan detail game dari Universe ID
            games_api_url = f"https://games.roblox.com/v1/games?universeIds={universe_id}"
            async with session.get(games_api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data") and len(data["data"]) > 0:
                        currently_public = True
                        game_data = data["data"][0]
                else:
                    print(f"Error saat mengambil detail game: Status {response.status}")
                    return

    except aiohttp.ClientError as e:
        print(f"Terjadi kesalahan jaringan: {e}")
        return
    except Exception as e:
        print(f"Terjadi kesalahan tak terduga: {e}")
        return

    # Inisialisasi status awal saat bot pertama kali jalan
    if map_is_public is None:
        map_is_public = currently_public
        status_str = "Publik" if currently_public else "Private"
        print(f"Status awal map Roblox '{game_data.get('name', 'N/A')}' (ID: {ROBLOX_PLACE_ID}) adalah: {status_str}")
        return

    # Periksa jika ada perubahan dari Private ke Publik
    if currently_public and not map_is_public:
        print(f"PERUBAHAN STATUS: Map '{game_data.get('name')}' sekarang PUBLIK!")
        notification_channel = bot.get_channel(NOTIFICATION_CHANNEL_ID)
        if notification_channel:
            embed = discord.Embed(
                title="🎉 Map Roblox Sekarang Publik! 🎉",
                description=f"Map **{game_data.get('name', 'N/A')}** sekarang sudah bisa diakses oleh semua orang!",
                color=discord.Color.blue()
            )
            game_url = f"https://www.roblox.com/games/{ROBLOX_PLACE_ID}"
            embed.add_field(name="🔗 Link Game", value=f"[Klik di sini untuk bermain]({game_url})", inline=False)
            embed.add_field(name="Pemain Aktif", value=game_data.get("playing", 0), inline=True)
            embed.add_field(name="Total Kunjungan", value=game_data.get("visits", 0), inline=True)

            # Coba dapatkan thumbnail game
            # Anda mungkin perlu menyesuaikan ini atau menggunakan API thumbnail terpisah
            # Untuk saat ini, kita biarkan kosong jika tidak ada

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
    else:
        bot.run(DISCORD_BOT_TOKEN)
