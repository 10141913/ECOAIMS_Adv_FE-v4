# Rekaman Historis Diskusi Teknis — ECO-AIMS FE

Dokumen ini merekam ringkasan keputusan teknis dan troubleshooting yang dilakukan selama penguatan operasional Frontend (FE) dan gateway auth.

## 2026-04-11 — Ringkasan perubahan utama

### 1) Script operasional FE
- `start.sh` diperluas untuk mode daemon/background, log + PID, serta env default untuk auth gateway dan konfigurasi server.
- Tujuan: menjalankan FE di server dengan perintah yang konsisten dan mudah dipantau (`install/start/daemon/stop/restart/status/logs`).

### 2) Perbaikan unduh Reports (menghindari report_file_not_found)
- Tombol unduh report yang sebelumnya mengarah langsung ke backend dapat gagal jika file report tidak ada di server.
- Strategi yang diterapkan: FE menyediakan endpoint download sendiri dan dapat melakukan proxy/fallback (graceful) bila backend tidak menyediakan file.

### 3) Gateway Login + Captcha + CSRF
- Gateway auth ditambahkan pada FE agar akses ke dashboard membutuhkan login.
- Alur yang distandarkan (sesuai checklist):
  - `GET /api/auth/captcha` terlebih dahulu untuk memperoleh cookie session + `csrf_token` + payload captcha.
  - `POST /api/auth/login` wajib mengirim:
    - Header `X-CSRF-Token: <csrf_token>`
    - Body JSON lengkap (`username,password,captcha,csrf_token`) dan opsional (`csrf_session,captcha_token`)
    - Cookie dari step captcha (via `credentials: include` di browser)
- Penanganan kasus lapangan:
  - `invalid_payload` sering terjadi karena body kosong `{}` (payload builder/quoting/copy-paste). Solusi: pastikan builder mengisi key yang tepat dan gunakan pendekatan aman saat testing (cookie jar + JSON yang benar).
  - `auth_failed` terjadi jika captcha/CSRF tidak match atau captcha sudah expired.

### 4) Mode proxy FE → BE untuk auth (disarankan produksi)
- FE diset agar endpoint auth yang dipanggil browser tetap di domain FE (`:8050`) dan FE meneruskan ke BE (`:8008`).
- Keuntungan: tidak perlu CORS lintas port, cookie lebih konsisten, dan troubleshooting lebih mudah.
- Indikator penting:
  - `GET http://<FE>:8050/api/auth/captcha` harus 200 dan meneruskan `Set-Cookie` dari BE.
  - Jika `GET .../api/auth/captcha` 404, itu biasanya respons BE yang diproxy (BE auth belum hidup atau base URL salah).

### 5) Captcha tidak muncul di UI
- Akar masalah yang sering: endpoint `/api/auth/captcha` tidak tersedia (404/503) sehingga `<img>` tidak punya `src`.
- Mitigasi UI di FE: menampilkan status error yang jelas dan men-disable tombol login sampai captcha berhasil dimuat.

### 6) Pengaturan visual captcha (UI-only)
- Perubahan visual captcha dapat dilakukan murni di FE (CSS pada halaman `/login`) tanpa mengubah generator captcha di BE, misalnya pengaturan `opacity`, `filter`, `box-shadow`, dan background container.

## Catatan operasional penting

- Jika akses `/` terasa tidak melewati login, biasanya browser masih punya cookie session; uji dengan incognito atau hapus cookie domain FE.
- Smoke check tanpa browser:
  - `curl -i http://127.0.0.1:8050/ | head -n 20` (harus 302 ke login jika belum auth)
  - `curl -i http://127.0.0.1:8050/api/auth/captcha | head -n 40` (harus 200 jika auth siap)
