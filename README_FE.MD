# ECO-AIMS Frontend (FE) — Operasional & Auth Gateway

Dokumen ini adalah ringkasan operasional untuk menjalankan Frontend ECO-AIMS (Dash/Flask) dan integrasinya dengan Backend (BE).

Referensi lengkap:
- Operator: `books/MANUAL_BOOK_ID.md`
- Peneliti: `books/MANUAL_BOOK_RESEARCH_ID.md`
- Riwayat diskusi teknis: `books/DISCUSSION_HISTORY_ID.md`

## Quick Start (Server)

Prasyarat:
- Python 3 + venv
- BE sudah berjalan (contoh: `http://127.0.0.1:8008`)

```bash
chmod +x start.sh
./start.sh install

export ECOAIMS_API_BASE_URL="http://127.0.0.1:8008"
export ECOAIMS_FRONTEND_HOST="0.0.0.0"
export ECOAIMS_FRONTEND_PORT="8050"

export ECOAIMS_AUTH_ENABLED=true
export ECOAIMS_AUTH_MODE=proxy
export ECOAIMS_AUTH_BACKEND_BASE_URL="http://127.0.0.1:8008"

./start.sh daemon
./start.sh status
./start.sh logs
```

URL:
- FE: `http://<HOST_FE>:8050/`
- Login: `http://<HOST_FE>:8050/login`

## Auth Gateway (FE → BE)

Mode produksi yang disarankan adalah proxy:
- Browser memanggil FE:
  - `GET /api/auth/captcha`
  - `POST /api/auth/login`
- FE meneruskan request ke BE:
  - `GET {ECOAIMS_AUTH_BACKEND_BASE_URL}/api/auth/captcha`
  - `POST {ECOAIMS_AUTH_BACKEND_BASE_URL}/api/auth/login`
- FE mem-forward `Set-Cookie` dari BE (ecoaims_captcha, ecoaims_csrf, ecoaims_session) sehingga browser tidak perlu CORS lintas port.

Variabel lingkungan:
- `ECOAIMS_AUTH_ENABLED` (default: true)
- `ECOAIMS_AUTH_MODE` (default: proxy)
- `ECOAIMS_AUTH_BACKEND_BASE_URL` (default: `ECOAIMS_API_BASE_URL`)

### Smoke Check (tanpa browser)

```bash
curl -i http://127.0.0.1:8050/ | head -n 20
curl -i http://127.0.0.1:8050/api/auth/captcha | head -n 40
```

Jika belum login:
- `/` harus `302` ke `/login?next=/`
- `/api/auth/captcha` harus `200` dan mengirim `Set-Cookie` dari BE

## HTTPS (Reverse Proxy)

Jika FE berada di belakang reverse proxy HTTPS dan proxy mengirim `X-Forwarded-Proto: https`:

```bash
export ECOAIMS_FORCE_HTTPS=true
export ECOAIMS_SESSION_COOKIE_SECURE=true
./start.sh restart
```

## Troubleshooting cepat

- Captcha tidak muncul di login:
  - cek `curl -i http://127.0.0.1:8050/api/auth/captcha | head -n 40`
  - jika 404/503, pastikan BE auth hidup dan `ECOAIMS_AUTH_BACKEND_BASE_URL` benar
- Akses `/` terasa tidak lewat login:
  - browser kemungkinan masih punya cookie session login; hapus cookie `127.0.0.1:8050` atau gunakan incognito
