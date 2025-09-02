# Discord Roblox Map Bot

Bot Discord ini dirancang untuk memberikan notifikasi tentang status map di Roblox dan menyambut anggota baru. Bot ini dapat dikonfigurasi sepenuhnya melalui command slash Discord, sehingga tidak perlu mengedit file kode setelah pengaturan awal.

## Fitur Utama

- **Notifikasi Status Map**: Secara otomatis memantau map Roblox tertentu dan memberitahu channel ketika statusnya berubah dari private ke publik, atau sebaliknya.
- **Pemeriksaan Manual**: Admin dapat secara manual memeriksa status map Roblox mana pun menggunakan command `/check [URL]`.
- **Pesan Selamat Datang**: Secara otomatis mengirimkan pesan selamat datang yang disematkan (embed) kepada anggota baru.
- **Konfigurasi Mudah**: Semua pengaturan (channel notifikasi, role yang di-ping, map yang dipantau) dapat dikelola melalui command `/setup`.

---

## Cara Menjalankan Bot Secara Lokal

1.  **Prasyarat**: Pastikan Anda memiliki Python 3.8 atau yang lebih baru terinstal.
2.  **Clone Repositori**: `git clone [URL repositori ini]`
3.  **Instal Dependensi**: `pip install -r requirements.txt`
4.  **Konfigurasi Token**: Buka file `bot.py` dan masukkan token bot Discord Anda di variabel `DISCORD_BOT_TOKEN`.
5.  **Jalankan Bot**: `python bot.py`
6.  **Gunakan Command `/setup`**: Setelah bot online di server Anda, gunakan command `/setup set` untuk mengkonfigurasi channel notifikasi, role yang akan di-ping, dan Place ID Roblox yang ingin Anda pantau.

---

## Cara Deploy di Oracle Cloud (Always Free Tier)

Panduan ini akan membantu Anda menjalankan bot ini 24/7 di instance Virtual Machine (VM) gratis dari Oracle Cloud.

### Langkah 1: Buat VM di Oracle Cloud

1.  **Buat Akun Oracle Cloud**: Jika Anda belum punya, daftar untuk akun gratis di [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/).
2.  **Buat Instance Compute**:
    *   Dari dashboard Oracle Cloud, navigasi ke **Compute > Instances**.
    *   Klik **Create instance**.
    *   **Name**: Beri nama instance Anda (misalnya, `discord-bot-vm`).
    *   **Image and shape**: Klik **Edit**. Pilih **Canonical Ubuntu** sebagai OS. Versi terbaru LTS biasanya pilihan yang baik. Pastikan instance tersebut memenuhi syarat untuk "Always Free eligible".
    *   **Networking**: Biarkan pengaturan default. Pastikan "Assign a public IPv4 address" dipilih.
    *   **Add SSH keys**: Di sini, Anda perlu menambahkan kunci SSH publik Anda. Jika Anda tidak memilikinya, Oracle menyediakan petunjuk untuk membuatnya. Simpan kunci privat Anda dengan aman; Anda akan membutuhkannya untuk terhubung.
    *   Klik **Create**. Tunggu beberapa menit hingga instance Anda selesai dibuat dan berjalan.

### Langkah 2: Hubungkan ke VM Anda

1.  Salin alamat IP publik dari instance Anda dari dashboard Oracle Cloud.
2.  Buka terminal atau command prompt di komputer Anda.
3.  Gunakan SSH untuk terhubung. Ganti `[path-to-your-private-key]` dengan path ke file kunci privat Anda dan `[public-ip-address]` dengan alamat IP publik instance Anda. Nama pengguna default untuk Ubuntu adalah `ubuntu`.

    ```bash
    ssh -i [path-to-your-private-key] ubuntu@[public-ip-address]
    ```

### Langkah 3: Siapkan Lingkungan Bot

1.  **Update Sistem**: Setelah terhubung, update daftar paket VM Anda.
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Instal Python dan Pip**:
    ```bash
    sudo apt install python3-pip python3-venv -y
    ```
3.  **Clone Repositori Bot**:
    ```bash
    git clone [URL repositori ini]
    cd [nama-direktori-repositori]
    ```
4.  **Buat Lingkungan Virtual**:
    ```bash
    python3 -m venv venv
    ```
5.  **Aktifkan Lingkungan Virtual**:
    ```bash
    source venv/bin/activate
    ```
6.  **Instal Dependensi**:
    ```bash
    pip install -r requirements.txt
    ```
7.  **Konfigurasi Token**:
    *   Buka file `bot.py` menggunakan editor teks seperti `nano`:
        ```bash
        nano bot.py
        ```
    *   Cari baris `DISCORD_BOT_TOKEN = "TOKEN_BOT_ANDA_DI_SINI"` dan ganti dengan token bot Anda yang sebenarnya.
    *   Simpan file dan keluar (di `nano`, tekan `Ctrl+X`, lalu `Y`, lalu `Enter`).

### Langkah 4: Jalankan Bot Secara Terus-Menerus dengan `systemd`

`systemd` adalah cara yang andal untuk memastikan bot Anda berjalan 24/7 dan secara otomatis restart jika terjadi crash atau server reboot.

1.  **Buat File Service `systemd`**:
    ```bash
    sudo nano /etc/systemd/system/discord_bot.service
    ```
2.  **Salin dan Tempel Konfigurasi Berikut**:
    *   Ganti `[path-to-your-bot-directory]` dengan path absolut ke direktori bot Anda (misalnya, `/home/ubuntu/discord-roblox-bot`). Anda bisa mendapatkan path ini dengan menjalankan `pwd` di direktori bot.
    *   Ganti `ubuntu` di baris `User` jika Anda menggunakan nama pengguna yang berbeda.

    ```ini
    [Unit]
    Description=Discord Bot for Roblox Map Status
    After=network.target

    [Service]
    User=ubuntu
    Group=ubuntu
    WorkingDirectory=[path-to-your-bot-directory]
    ExecStart=[path-to-your-bot-directory]/venv/bin/python3 [path-to-your-bot-directory]/bot.py
    Restart=always
    RestartSec=5s

    [Install]
    WantedBy=multi-user.target
    ```

3.  **Aktifkan dan Jalankan Service**:
    *   Muat ulang `systemd` untuk mengenali service baru Anda:
        ```bash
        sudo systemctl daemon-reload
        ```
    *   Aktifkan service agar berjalan saat boot:
        ```bash
        sudo systemctl enable discord_bot.service
        ```
    *   Mulai service sekarang juga:
        ```bash
        sudo systemctl start discord_bot.service
        ```

4.  **Periksa Status Service**:
    *   Anda dapat memeriksa apakah bot Anda berjalan dengan benar dengan command:
        ```bash
        sudo systemctl status discord_bot.service
        ```
    *   Untuk melihat log bot secara real-time, Anda bisa menggunakan:
        ```bash
        sudo journalctl -u discord_bot.service -f
        ```

### Langkah 5: Konfigurasi Bot di Discord

Bot Anda sekarang berjalan di cloud! Langkah terakhir adalah mengkonfigurasinya di server Discord Anda:

1.  Undang bot ke server Anda dengan izin yang benar.
2.  Gunakan command `/setup set` untuk memberi tahu bot di channel mana harus mengirim notifikasi dan role mana yang harus di-ping.

Selamat! Bot Anda sekarang sepenuhnya di-deploy dan dikonfigurasi.
