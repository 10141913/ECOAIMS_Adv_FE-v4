# ECO-AIMS Frontend

Dashboard energi berbasis Dash & Plotly untuk pemantauan, forecasting, optimisasi, precooling, BMS, dan laporan.

## Ringkas (Operator)
- Jalankan pipeline standar: `make check` (lint + unit test + audit-callbacks + smoke)
- Jalankan pipeline lengkap: `make check-all` (check + smoke-browser)
- Checklist rilis/hardening: lihat `docs/RELEASE_CHECKLIST.md`
- Buku panduan operator (Bahasa Indonesia): lihat `books/MANUAL_BOOK_ID.md`
- Manual Book untuk Peneliti (Bahasa Indonesia): lihat `books/MANUAL_BOOK_RESEARCH_ID.md`
- Jalankan stack kanonik end-to-end: `make stack-canonical` (BE 8008 + FE 8050)
- Diagnostik one-liner: `make doctor-stack` (stop FE stale, verifikasi backend, start FE, verifikasi runtime)
- Smoke: `make smoke` (runtime) • `make smoke-browser` (Playwright, opsional)

## Quickstart: Menjalankan FE saja (Dashboard)
Jika backend sudah berjalan (default canonical: `http://127.0.0.1:8008`), Anda bisa menjalankan FE langsung dari repo ini:

```bash
ECOAIMS_API_BASE_URL=http://127.0.0.1:8008 \
ECOAIMS_DASH_HOST=127.0.0.1 \
ECOAIMS_DASH_PORT=8050 \
./ecoaims_frontend_env/bin/python -m ecoaims_frontend.app
```

Buka:
- UI: `http://127.0.0.1:8050/`
- Runtime: `http://127.0.0.1:8050/__runtime`

## Prosedur Operasional (Start/Restart/Always-on/Tracing)
Bagian ini merangkum langkah operasional yang benar setelah Anda membuka folder repo BE dan repo FE.

### 1) Setup sekali per terminal (disarankan)
Di terminal mana pun (terminal FE atau BE), set path repo dan `ecoaims` di PATH:

```bash
export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
export PATH="$ECOAIMS_FE_REPO/bin:$PATH"
```

### 2) Start dari awal (pilih skenario)
#### A. Canonical lane (demo/rilis, fail-closed) — start BE+FE dari repo FE
Jalankan dari terminal mana pun:

```bash
ecoaims up --mode canonical
ecoaims status
```

Validasi:
- FE runtime: `http://127.0.0.1:8050/__runtime`
- Backend: `http://127.0.0.1:8008/api/startup-info`

#### B. External lane (BE repo terpisah, mis. 8009) — start BE dari repo BE, FE dari repo FE
1) Start BE (di terminal BE atau terminal mana pun):

```bash
make -C "$ECOAIMS_BE_REPO" stack-up API_HOST=127.0.0.1 API_PORT=8009 FE_REPO="$ECOAIMS_FE_REPO"
```

2) Start FE pointing ke 8009 (di terminal FE atau terminal mana pun):

```bash
ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 \
ECOAIMS_REQUIRE_CANONICAL_POLICY=false \
ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true \
make -C "$ECOAIMS_FE_REPO" run-frontend-canonical
```

3) Refresh registry/cache (disarankan setiap backend restart/berubah):

```bash
BACKEND=http://127.0.0.1:8009 make -C "$ECOAIMS_FE_REPO" doctor-stack
```

### 3) Restart (aman untuk operasional)
Canonical:

```bash
ecoaims restart --mode canonical
```

External (BE repo terpisah 8009):

```bash
make -C "$ECOAIMS_BE_REPO" stack-restart API_HOST=127.0.0.1 API_PORT=8009 FE_REPO="$ECOAIMS_FE_REPO"
```

### 4) Stop (aman)
Stop semua port canonical/devtools:

```bash
ecoaims down --mode all
```

Stop stack BE repo terpisah (8009):

```bash
make -C "$ECOAIMS_BE_REPO" stack-down API_HOST=127.0.0.1 API_PORT=8009 FE_REPO="$ECOAIMS_FE_REPO"
```

### 5) Tracing ON (header tracing FE→BE)
Tracing header default OFF. Untuk mengaktifkan dan memberi identitas build:

```bash
export ECOAIMS_HTTP_TRACE_HEADERS=true
export ECOAIMS_FE_BUILD_ID="demo-$(date +%Y%m%d-%H%M%S)"
export ECOAIMS_FE_VERSION="v2"
```

Catatan: env di atas harus sudah diset sebelum start FE (lalu restart FE agar berlaku).

### 6) Always-on (2 service terpisah)
Always-on dilakukan dengan: generate file service sekali → install ke service manager OS (launchd/systemd). Lihat bagian Always-on (2 service terpisah) di bawah.

## Satu Perintah (Start/Stop/Restart)
Tujuan: menjalankan BE+FE dengan satu perintah, serta stop/restart dengan satu perintah.

### Dari repo FE (paling sederhana)
- Canonical (BE 8008 + FE 8050):

```bash
make up MODE=canonical
```

- Devtools (BE 8009 + FE 8060):

```bash
make up MODE=devtools
```

- External backend (mis. BE 8009 eksternal; hanya start FE):

```bash
make up MODE=external BACKEND=http://127.0.0.1:8009
```

- Stop / restart / status:

```bash
make down MODE=all
make restart MODE=canonical
make status MODE=canonical
```

### Dari mana saja (PATH)
Tambahkan `bin/` repo FE ke PATH sekali saja:

```bash
export PATH="/path/ke/ECOAIMS_Adv_FE v-4/bin:$PATH"
```

Contoh path repo FE Anda:

```bash
export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
export PATH="$ECOAIMS_FE_REPO/bin:$PATH"
```

Lalu jalankan:

```bash
ecoaims up --mode canonical
ecoaims down --mode all
ecoaims restart --mode canonical
ecoaims status
```

Jika repo FE/BE tidak berada di folder yang sama, set:
- `ECOAIMS_FE_REPO=/path/ke/ECOAIMS_Adv_FE v-4`
- `ECOAIMS_BE_REPO=/path/ke/ECOAIMS_Adv_BE v-4`

### Menjalankan BE repo terpisah dari terminal FE (Crossrepo)
Catatan: `ecoaims up --mode canonical` menyalakan backend canonical yang dibundling di repo FE (port 8008). Jika Anda ingin menyalakan backend dari repo BE terpisah, gunakan Makefile repo BE dari terminal mana pun (termasuk terminal FE) dengan `make -C`.

Start BE+FE sekaligus (background, bisa stop/restart/status):

```bash
make -C "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4" \
  stack-up API_HOST=127.0.0.1 API_PORT=8009 \
  FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
```

Stop/restart/status:

```bash
make -C "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4" \
  stack-down API_HOST=127.0.0.1 API_PORT=8009 \
  FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"

make -C "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4" \
  stack-restart API_HOST=127.0.0.1 API_PORT=8009 \
  FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"

make -C "/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4" \
  stack-status API_HOST=127.0.0.1 API_PORT=8009 \
  FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
```

## Fitur UI (Ketahanan & Pengalaman Pengguna)
- **Graceful Degradation:** Sistem dapat menangani kegagalan (misalnya karena backend error atau rate limit) tanpa blank screen, dan akan memunculkan banner notifikasi yang informatif.
- **Browser Caching:** UI mengingat pilihan *dropdown* dan *slider* Anda antar perpindahan tab menggunakan `dcc.Store` dan mekanisme `persistence` browser.
- **End-to-End Testing:** Terdapat Playwright E2E automation (`scripts/smoke_browser.py`) yang akan menguji seluruh fitur antar tab (Monitoring, Optimization, Precooling, Forecasting, Settings, Reports, About) secara otomatis.

## Observability (Ops Watch)
Tab **Reports** memiliki tombol **Backend Ops Watch** untuk menampilkan ringkasan monitoring backend (plain text) di dalam modal UI.

Prasyarat (di BE):
- BE harus menyediakan endpoint `GET /ops/watch` (contoh: `http://127.0.0.1:8008/ops/watch?tail=200&minutes=60`) yang mengembalikan plain text.

Cara pakai (di FE):
- Buka tab **Reports** → klik **Backend Ops Watch** → gunakan **Refresh** untuk update.
- Jika backend belum menyediakan endpoint tersebut, FE akan menampilkan pesan “ops-watch belum tersedia di backend”.

Catatan:
- Ini membantu troubleshooting kasus “Waiting for backend … error_class=backend_http_error” tanpa perlu membuka terminal.

## Always-on (2 service terpisah)
Tujuan: BE dan FE berjalan otomatis dan auto-restart jika crash, dengan log terpisah. Sangat disarankan untuk operasional jangka panjang agar tidak bergantung pada terminal yang terbuka.

### Generate file service (macOS launchd + Linux systemd)
Set path repo FE/BE, lalu generate:

```bash
export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
./ecoaims_frontend_env/bin/python scripts/gen_always_on_services.py
```

Output file akan dibuat di:
- `ops/generated/launchd/` (macOS)
- `ops/generated/systemd/` (Linux)

### Langkah Instalasi (macOS / launchd)
1. Salin file plist yang di-generate ke folder `LaunchAgents` Anda:
```bash
cp ops/generated/launchd/com.ecoaims.backend.8009.plist ~/Library/LaunchAgents/
cp ops/generated/launchd/com.ecoaims.frontend.8050.plist ~/Library/LaunchAgents/
```

2. Muat (Load) service agar berjalan di background secara otomatis:
```bash
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.backend.8009.plist
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
```

3. (Opsional) Untuk mematikan service:
```bash
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.backend.8009.plist
```
- Log: `ops/generated/logs/`

### Install di macOS (launchd)
User-level (jalankan saat login user):

```bash
cp ops/generated/launchd/*.plist ~/Library/LaunchAgents/
launchctl unload ~/Library/LaunchAgents/com.ecoaims.backend.8009.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist 2>/dev/null || true
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.backend.8009.plist
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
```

Stop/disable:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.backend.8009.plist
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
```

### Install di Linux (systemd)
Copy file `.service` ke `/etc/systemd/system/` (butuh sudo), lalu:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now com.ecoaims.backend.8009.service
sudo systemctl enable --now com.ecoaims.frontend.8050.service
sudo systemctl status com.ecoaims.backend.8009.service
sudo systemctl status com.ecoaims.frontend.8050.service
```

Catatan:
- Mode `external` akan menjalankan FE dengan `ECOAIMS_REQUIRE_CANONICAL_POLICY=false` dan `ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true`.
- Mode `canonical` menarget backend 8008 dan FE 8050 (strict lane).

## Health Contract Dashboard (logging periodik)
Tujuan: mencatat status integrasi secara periodik (startup-info, manifest hash, hash endpoint_map) ke file log agar mismatch bisa ditrace (apakah BE berubah atau FE belum refresh).

Start/stop/status logger:

```bash
make health-contract-start
make health-contract-status
make health-contract-report
make health-contract-stop
```

Output default:
- `.run/health_contract.jsonl` (JSONL; 1 baris per interval)
- `.run/health_contract_last.json` (snapshot terakhir)

## Watcher (doctor+smoke semi-otomatis)
Secara default, `doctor-stack` dan `smoke` tidak berjalan otomatis. Jika Anda ingin otomatis menjalankan `doctor-stack` saat backend berubah (contract hash / registry endpoints), jalankan watcher:

```bash
BACKEND=http://127.0.0.1:8009 make watch-backend-start
make watch-backend-status
make watch-backend-stop
```

Catatan:
- Watcher ini memanggil `make doctor-stack` saat terdeteksi perubahan di `/api/startup-info` atau `/api/contracts/index`.
- Jika Anda ingin sekaligus menjalankan `make smoke` setelah `doctor-stack`, gunakan:

```bash
BACKEND=http://127.0.0.1:8009 WITH_SMOKE=1 make watch-backend-start
```

## Fitur Utama
- Monitoring real-time (speedometer Solar/Wind/Battery/Grid), tren, dan komparasi bauran energi.
- Forecasting konsumsi & produksi (harian/jam) dengan kontrol periode.
- Optimization strategi distribusi (prioritas Renewable/Battery/Grid) dan rekomendasi.
- Precooling / LAEOPF: status, jadwal, simulasi, skenario, KPI, alerts, audit, apply.
- BMS: SOC, tegangan, arus, suhu, kontrol charge/discharge, grafik multi-aksi.
- Reports: snapshot, tren, kualitas data, ekspor CSV, drilldown sesi.
- Help/FAQ & About: panduan, tim, lisensi.

## Prasyarat
- Python 3.12 disarankan (minimal Python 3.x)
- Virtual environment disarankan (folder default repo: `ecoaims_frontend_env/`)
- Dependensi inti: dash, plotly, pandas, requests

## Quickstart (Pilih Mode)

### Mode 1 — Canonical (paling stabil, fail-closed)
Gunakan ini jika Anda ingin semua tab/fitur bekerja dengan kontrak & policy kanonik.

```bash
make stack-canonical
```

- FE: http://127.0.0.1:8050/
- BE: http://127.0.0.1:8008/
- Log stack-canonical: `.run/backend_canonical.log` dan `.run/frontend_canonical.log`
- Validasi cepat:
  - FE runtime: `make show-frontend-runtime`
  - Backend: `curl -s http://127.0.0.1:8008/api/startup-info | python -m json.tool`

### Mode 2 — External/Devtools Backend (mis. BE 8009)
Gunakan ini jika FE harus pointing ke backend lain (mis. repo BE terpisah pada port 8009).

```bash
ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 \
ECOAIMS_REQUIRE_CANONICAL_POLICY=false \
ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true \
make run-frontend-canonical
```

- FE tetap di http://127.0.0.1:8050/
- Validasi cepat: buka `http://127.0.0.1:8050/__runtime` dan pastikan `ecoaims_api_base_url=http://127.0.0.1:8009`

### Mode 3 — Devtools Stack bawaan repo (BE 8009 + FE 8060)
Untuk menjalankan stack devtools yang disediakan repo ini:

```bash
make stack-devtools
```

## Konfigurasi FE
- Stop FE jika port terpakai:
  - `make stop-frontend` (default FE_PORT=8050)
  - `FE_PORT=8050 make stop-frontend` (eksplisit)
- Start FE deterministik (single-process):
  - `make run-frontend-canonical`
- Runtime endpoint:
  - `make show-frontend-runtime` atau buka `http://127.0.0.1:8050/__runtime`

## Integrasi Backend
- Default canonical backend di repo ini: FastAPI `ecoaims_backend.devtools.canonical_fastapi_app:app` (default 127.0.0.1:8008)
- Binding base URL backend:
  - FE membaca `ECOAIMS_API_BASE_URL` (runtime) yang di-set oleh `ECOAIMS_API_BASE_URL_CANONICAL` pada target Makefile `run-frontend-canonical`

### Prinsip Integrasi (supaya “harmonis”)
- FE dan BE harus menunjuk instance yang sama: cek `http://127.0.0.1:8050/__runtime` dan `http://127.0.0.1:8008/api/startup-info`
- Kontrak + registry:
  - `GET /api/contracts/index` harus memuat endpoint yang dipakai tab yang sedang dibuka
- Lane canonical (fail-closed):
  - Gunakan `ECOAIMS_REQUIRE_CANONICAL_POLICY=true` (default pada `make stack-canonical`)
- Lane non-canonical (lebih toleran untuk backend eksternal):
  - Gunakan `ECOAIMS_REQUIRE_CANONICAL_POLICY=false` dan `ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true`

## Precooling API (ringkas)
- Endpoint utama:
  - GET `/api/precooling/status`, `/schedule`, `/scenarios`, `/kpi`, `/alerts`, `/audit`, `/settings`, `/settings/default`
  - POST `/api/precooling/simulate`, `/apply`, `/force_fallback`, `/settings`, `/settings/validate`, `/settings/reset`, `/settings/apply`
- Persistensi settings (backend): `output/precooling/settings.json`, `output/precooling/settings_active.json`
- Refresh interval default: 10 detik (`PRECOOLING_REFRESH_INTERVAL_MS`)

## Operasional & Diagnostik

### Doctor
- Diagnostik satu tombol (stop FE stale, verify backend, start FE, verify runtime):

```bash
make doctor-stack
```

- Menarget backend tertentu:

```bash
BACKEND=http://127.0.0.1:8009 make doctor-stack
```

- Mode verifikasi backend:
  - strict (default): cek tambahan seperti CORS preflight, gzip optimize, dll
  - lenient (untuk backend eksternal yang tidak menyediakan semua endpoint opsional):

```bash
ECOAIMS_DOCTOR_STRICT=false BACKEND=http://127.0.0.1:8009 make doctor-backend-only
```

### Banner yang sering muncul
- Backend connected but contract mismatch:
  - Cek `GET /api/startup-info` dan `GET /api/contracts/index` di backend
  - Jalankan `make doctor-stack` untuk refresh registry/manifest FE
- Monitoring/Optimization blocked:
  - Biasanya karena lane canonical + policy/identity/contract belum OK
  - Pastikan Anda menjalankan `make stack-canonical` (untuk 8008) atau non-canonical env (untuk 8009)

### Catatan UX
- Optimizer Backend (shared) dipakai oleh Precooling/LAEOPF. Tidak mengubah hasil `POST /optimize` pada tab Optimization.
- Energy Source di “Precooling Status Overview” berasal dari status backend (schedule aktif), bukan otomatis mengikuti dropdown UI.

## Smoke & Load
- Runtime smoke:
  
  ```bash
  make smoke
  ```
  
- Browser smoke (Playwright, opsional):
  
  ```bash
  ./ecoaims_frontend_env/bin/python -m pip install -r ecoaims_frontend/requirements-dev.txt
  ./ecoaims_frontend_env/bin/python -m playwright install chromium
  make smoke-browser
  ```
  
- Stress loop (FE-only):
  
  ```bash
  export ECOAIMS_SMOKE_DASH_LOOP_ITERS=5000
  export ECOAIMS_SMOKE_DASH_LOOP_TARGETS=monitoring,comparison
  export ECOAIMS_SMOKE_DASH_LOOP_SLEEP_MS=0
  ./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
  ```

## Struktur Folder

```plaintext
ecoaims_frontend/
├── app.py
├── config.py
├── layouts/
├── callbacks/
├── components/
├── services/
├── assets/
├── data/
├── requirements.txt
└── README.md
```

## Kontribusi
- Buat pull request dengan perubahan terstruktur (layouts/callbacks/components/services).
- Ikuti modularitas yang ada dan jalankan `make check` sebelum mengajukan PR.

## Environment Variables (yang sering dipakai)
- `ECOAIMS_API_BASE_URL` / `ECOAIMS_API_BASE_URL_CANONICAL`: base URL backend
- `ECOAIMS_REQUIRE_CANONICAL_POLICY`: fail-closed canonical lane (true/false)
- `ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO`: izinkan startup-info minimal untuk backend eksternal (true/false)
- `ECOAIMS_STRICT_CONTRACT_VERSION`: paksa contract_version harus match (true/false)
- `ECOAIMS_DOCTOR_STRICT`: strict backend checks (true/false)
- `FE_HOST`, `FE_PORT`, `BACKEND`: override target Makefile saat menjalankan doctor/FE
