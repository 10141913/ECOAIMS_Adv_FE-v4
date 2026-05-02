# Setup Colima untuk ECOAIMS Docker Deployment

Panduan ini menjelaskan cara menginstal dan menggunakan **Colima** (alternatif Docker Desktop gratis untuk macOS) agar dapat menjalankan `docker compose up --build` untuk aplikasi ECOAIMS frontend dan backend.

---

## Prasyarat

- macOS (Intel atau Apple Silicon)
- Homebrew (jika belum terinstal, lihat langkah 1)
- File Docker yang sudah ada di repo:
  - [`Dockerfile`](Dockerfile)
  - [`.dockerignore`](.dockerignore)
  - [`docker-compose.yml`](docker-compose.yml)

---

## 1. Install Homebrew (jika belum ada)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Setelah instalasi, ikuti petunjuk **Next Steps** yang muncul di terminal untuk menambahkan Homebrew ke PATH.

Verifikasi:

```bash
brew --version
```

---

## 2. Install Colima

```bash
brew install colima
```

---

## 3. Start Colima VM

Jalankan Colima dengan alokasi resource yang memadai:

```bash
colima start --cpu 4 --memory 4 --disk 50
```

Penjelasan parameter:
- `--cpu 4` — 4 core CPU
- `--memory 4` — 4 GB RAM
- `--disk 50` — 50 GB disk space

> **Catatan untuk Apple Silicon (M1/M2/M3):** Colima secara otomatis menggunakan virtualisasi ARM-native. Tidak perlu konfigurasi tambahan.

---

## 4. Install Docker CLI

Colima hanya menyediakan *runtime* container. Anda tetap perlu Docker CLI untuk menjalankan perintah `docker` dan `docker compose`.

```bash
brew install docker docker-compose
```

---

## 5. Verifikasi Instalasi

Pastikan Colima berjalan dan Docker CLI terhubung:

```bash
# Cek status Colima
colima status

# Cek info Docker
docker info

# Pastikan context Docker mengarah ke Colima
docker context show
```

Output `docker context show` harus menampilkan `colima` (bukan `desktop`).

---

## 6. Build dan Jalankan ECOAIMS

Sekarang Anda dapat menjalankan ECOAIMS frontend dan backend:

```bash
# Dari root direktori proyek
docker compose up --build
```

Perintah ini akan:
1. Membuild image Docker untuk `ecoaims-frontend` dan `ecoaims-backend`
2. Menjalankan kedua container dalam satu network (`ecoaims-network`)
3. Mengekspos port:
   - **Frontend:** `http://localhost:8050`
   - **Backend:** `http://localhost:8008`

Untuk menjalankan di background (detached mode):

```bash
docker compose up --build -d
```

---

## 7. Akses Dashboard

Buka browser dan akses:

```
http://localhost:8050
```

Dashboard ECOAIMS akan muncul. Jika backend juga berjalan, data akan terisi secara otomatis.

---

## 8. Perintah Colima yang Berguna

| Perintah | Deskripsi |
|---|---|
| `colima start` | Start Colima VM |
| `colima stop` | Stop Colima VM (tanpa menghapus) |
| `colima restart` | Restart Colima VM |
| `colima status` | Cek status Colima |
| `colima ssh` | SSH ke dalam VM Colima |
| `colima delete` | Hapus VM Colima (data hilang) |
| `colima prune` | Hapus semua VM yang tidak digunakan |

---

## 9. Troubleshooting

### Port 8050 atau 8008 sudah dipakai

Hentikan proses yang menggunakan port tersebut:

```bash
# Cek proses di port 8050
lsof -i :8050

# Hentikan proses (ganti PID dengan angka yang muncul)
kill -9 <PID>
```

Atau jalankan ulang dengan environment variables:

```bash
ECOAIMS_FRONTEND_PORT=8051 docker compose up --build
```

### Colima tidak bisa start

Coba reset Colima:

```bash
colima stop
colima delete
colima start --cpu 4 --memory 4 --disk 50
```

### Docker context masih mengarah ke Docker Desktop

```bash
# Lihat context yang tersedia
docker context ls

# Switch ke colima
docker context use colima
```

### Container tidak bisa reach `host.docker.internal`

Di Colima, `host.docker.internal` mungkin tidak tersedia secara default. Solusi:

1. Gunakan IP host langsung (`192.168.x.x`) atau
2. Pastikan service-service dalam `docker-compose.yml` saling terhubung via service name (sudah dikonfigurasi otomatis)

### Resource tidak cukup

Ubah alokasi resource saat start:

```bash
colima stop
colima start --cpu 6 --memory 8 --disk 100
```

---

## Referensi

- [Colima GitHub](https://github.com/abiosoft/colima)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
