# Buku Panduan (Manual Book) — ECO-AIMS Frontend

Dokumen ini menjelaskan cara mengoperasikan ECO-AIMS Frontend (FE) secara berurutan, memahami fungsi setiap fitur, serta hal-hal penting untuk stabilitas, keamanan, dan troubleshooting. Panduan ditulis untuk operator/peneliti yang menjalankan FE terintegrasi dengan Backend (BE).

Untuk kebutuhan penelitian (protokol eksperimen, template pencatatan, parameter sweep), gunakan juga: `books/MANUAL_BOOK_RESEARCH_ID.md`.
Ringkasan operasional server FE ada di `README_FE.MD`. Untuk jejak keputusan teknis, lihat `books/DISCUSSION_HISTORY_ID.md`.

## Daftar Isi
- 1. Gambaran Umum
- 2. Konsep Kunci (Lane, Kontrak, Registry, Policy)
- 3. Prasyarat & Persiapan
- 4. Menjalankan Sistem (Mode Canonical vs External/Devtools)
- 5. Verifikasi Awal (Checklist sebelum operasional)
- 6. Alur Operasi Harian (Runbook ringkas)
- 7. Panduan Per Tab/Fitur
- 8. Ekspor, Audit, dan Artefak Verifikasi
- 9. Troubleshooting (Kasus umum & langkah pemulihan)
- 10. Catatan Keamanan & Hardening
- 11. Lampiran: Perintah Make & Environment Variables

---

## 1. Gambaran Umum
ECO-AIMS Frontend adalah dashboard berbasis Dash/Plotly yang menyediakan:
- Monitoring energi (Solar/Wind/Battery/Grid) dan komparasi.
- Forecasting (konsumsi/produksi) berbasis periode.
- Optimization distribusi energi (simulasi & rekomendasi).
- Precooling/LAEOPF (status, jadwal, simulasi, kandidat, apply, KPI, audit).
- BMS (indikator & kontrol).
- Reports (impact, trend, drilldown sesi, export).

FE terintegrasi dengan BE melalui HTTP API. FE memverifikasi “kecocokan kontrak” agar UI tidak menampilkan data yang salah.

---

## 2. Konsep Kunci (Lane, Kontrak, Registry, Policy)
Sebelum mengoperasikan, pahami istilah berikut:

### 2.1 Lane/Mode Operasi
- Canonical lane (fail-closed): FE memblok fitur jika identity/policy/kontrak tidak sesuai. Dipakai untuk kondisi “stabil & ketat”.
- External/Devtools lane (lebih toleran): FE menerima backend eksternal yang mungkin berbeda versi, dengan fallback/gating yang jelas (tanpa crash).

### 2.2 Kontrak, Registry, dan Manifest
- Kontrak: “bentuk data” (JSON shape) yang diharapkan FE untuk setiap endpoint.
- Registry: indeks kontrak dari backend (`GET /api/contracts/index`) yang memetakan endpoint ke manifest/kontrak.
- Manifest: paket kontrak yang menjelaskan endpoint map dan required fields.

### 2.3 Policy (Gate Operasional)
Backend dapat menyediakan policy/gating yang menentukan fitur mana “live”, “degraded”, atau “blocked”. Pada canonical lane, policy bersifat mengikat (FE tidak memakai fallback lokal).

---

## 3. Prasyarat & Persiapan
### 3.1 Prasyarat Teknis
- Python 3.12 disarankan.
- Virtual environment disarankan: `ecoaims_frontend_env/`.
- Port default:
  - BE canonical: 8008
  - FE: 8050
  - BE devtools/external (contoh): 8009

Instalasi dependency (sekali per mesin/venv):

```bash
python3 -m venv ecoaims_frontend_env
./ecoaims_frontend_env/bin/python -m pip install -U pip
./ecoaims_frontend_env/bin/python -m pip install -r ecoaims_frontend/requirements.txt
```
Opsional (untuk test/smoke di repo FE):


```bash
./ecoaims_frontend_env/bin/python -m pip install -r ecoaims_frontend/requirements-dev.txt
./ecoaims_frontend_env/bin/python -m playwright install chromium
```

### 3.2 Struktur Repo (ringkas)
- `ecoaims_frontend/`: aplikasi FE (Dash)
- `ecoaims_backend/`: backend kanonik yang dibundling di repo ini (untuk mode canonical)
- `scripts/`: tool operasional (doctor, smoke, verify, dll)
- `docs/`: dokumentasi tambahan

## 3.3 Fitur Keandalan UI (UI Reliability)

Untuk kenyamanan Anda sebagai operator, Frontend (FE) telah dilengkapi dengan berbagai fitur keandalan:
- **Penyimpanan State (Browser Caching):** Pilihan *dropdown*, input, dan *slider* Anda (misalnya di tab Precooling atau Reports) akan secara otomatis tersimpan dan tidak akan hilang meskipun Anda berpindah-pindah antar tab.
- **Graceful Degradation:** Apabila simulasi atau pemrosesan data memakan waktu terlalu lama atau Backend sedang terganggu, layar tidak akan menjadi putih/kosong. Sebaliknya, sistem akan menampilkan notifikasi atau *banner* kesalahan yang ramah.
- **Observability (Ops Watch):** Tab Reports menyediakan tombol **Backend Ops Watch** untuk melihat ringkasan monitoring backend (plain text) langsung di UI, berguna saat muncul banner “Waiting for backend”.

---

## 4. Menjalankan Sistem (Mode Canonical vs External/Devtools)
### 4.1 Mode Canonical (Disarankan untuk stabilitas)
Mode ini menyalakan BE kanonik (8008) + FE (8050) dan melakukan warm-up.

```bash
make stack-canonical
```

Yang Anda harapkan:
- FE: http://127.0.0.1:8050/
- Banner “Canonical integration verified”
- Log: `.run/backend_canonical.log` dan `.run/frontend_canonical.log`

### 4.1.1 Menjalankan FE saja (Dashboard) dari repo FE
Gunakan opsi ini jika backend sudah berjalan (mis. backend canonical 8008 atau backend eksternal 8009), dan Anda hanya ingin menyalakan FE.

```bash
ECOAIMS_API_BASE_URL=http://127.0.0.1:8008 \
ECOAIMS_DASH_HOST=127.0.0.1 \
ECOAIMS_DASH_PORT=8050 \
./ecoaims_frontend_env/bin/python -m ecoaims_frontend.app
```

Validasi:
- UI: `http://127.0.0.1:8050/`
- Runtime: `http://127.0.0.1:8050/__runtime` (cek `ecoaims_api_base_url`)

### 4.2 Mode External/Devtools Backend (mis. BE di port 8009)
Gunakan saat BE Anda adalah repo terpisah/varian lain.

```bash
ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 \
ECOAIMS_REQUIRE_CANONICAL_POLICY=false \
ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true \
make run-frontend-canonical
```

Catatan penting:
- Mode ini tidak menjanjikan semua tab “live” jika BE tidak menyediakan endpoint/kontrak tertentu.
- Jika Anda butuh verifikasi yang ketat, gunakan canonical lane (8008).

### 4.3 Mode Devtools Stack (Bawaan repo; BE 8009 + FE 8060)

```bash
make stack-devtools
```

### 4.4 Satu Perintah (Start/Stop/Restart/Status)
Tujuan: menjalankan stack dengan satu perintah, dari terminal mana saja (setelah PATH + repo path diset).

Setup sekali per terminal:

```bash
export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
export PATH="$ECOAIMS_FE_REPO/bin:$PATH"
```

Perintah operasional:

```bash
ecoaims up --mode canonical
ecoaims status
ecoaims restart --mode canonical
ecoaims down --mode all
```

Catatan:
- `--mode canonical` menyalakan backend canonical yang dibundling di repo FE (port 8008) + FE (8050).
- Jika Anda menyalakan BE repo terpisah (mis. 8009), gunakan mode `external` untuk FE (atau gunakan Makefile repo BE untuk start/stop stack 8009).

### 4.5 Always-on (2 service terpisah)
Tujuan: BE dan FE berjalan otomatis dan auto-restart jika crash, dengan log terpisah. Sangat disarankan untuk fase penelitian agar Anda tidak perlu membuka terminal terus-menerus.

Alurnya:
1) Generate file service sekali
2) Install ke service manager OS (launchd/systemd)

Generate file service (macOS launchd + Linux systemd):

```bash
export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
./ecoaims_frontend_env/bin/python scripts/gen_always_on_services.py --mode canonical
```

Output:
- `ops/generated/launchd/` (macOS)
- `ops/generated/systemd/` (Linux)
- log: `ops/generated/logs/`

Langkah instalasi (Contoh untuk macOS / launchd):
1. Salin file plist yang di-generate ke folder `LaunchAgents` Anda:
```bash
cp ops/generated/launchd/com.ecoaims.backend.8008.plist ~/Library/LaunchAgents/
cp ops/generated/launchd/com.ecoaims.frontend.8050.plist ~/Library/LaunchAgents/
```
2. Muat (Load) service agar berjalan di background:
```bash
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.backend.8008.plist
launchctl load -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
```
3. (Opsional) Untuk mematikan service:
```bash
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
launchctl unload -w ~/Library/LaunchAgents/com.ecoaims.backend.8008.plist
```

---

## 5. Verifikasi Awal (Checklist sebelum operasional)
Lakukan sebelum menjalankan skenario penelitian/operasional.

### 5.1 Verifikasi runtime FE
Buka:
- `http://127.0.0.1:8050/__runtime`

Pastikan:
- `ecoaims_api_base_url` sesuai backend target (8008 atau 8009)

### 5.2 Doctor (verifikasi end-to-end)
One-liner yang aman untuk operator:

```bash
make doctor-stack
```

Menarget backend tertentu:

```bash
BACKEND=http://127.0.0.1:8009 make doctor-stack
```

### 5.3 Smoke (uji cepat stabilitas)
- Runtime smoke:

```bash
make smoke
```

- Browser smoke (opsional, untuk memastikan UI/tab terbuka baik):

```bash
./ecoaims_frontend_env/bin/python -m pip install -r ecoaims_frontend/requirements-dev.txt
./ecoaims_frontend_env/bin/python -m playwright install chromium
make smoke-browser
```

### 5.4 Observabilitas & Traceability (disarankan)
Bagian ini tidak mengubah behavior bisnis aplikasi, tetapi membantu trace masalah integrasi (mismatch, backend down, drift kontrak).

#### Tracing header FE→BE (opsional)
Default tracing OFF. Untuk demo/eksperimen, aktifkan dan set build id:

```bash
export ECOAIMS_HTTP_TRACE_HEADERS=true
export ECOAIMS_FE_BUILD_ID="demo-$(date +%Y%m%d-%H%M%S)"
export ECOAIMS_FE_VERSION="v2"
```

Catatan:
- Env tracing harus diset sebelum start FE, lalu restart FE agar berlaku.

#### Health Contract Dashboard (logging periodik)
Mulai logger periodik (mencatat `/__runtime`, `/api/startup-info`, `/api/contracts/index`):

```bash
make health-contract-start
make health-contract-report
```

Stop:

```bash
make health-contract-stop
```

Output default:
- `.run/health_contract.jsonl` (JSONL; 1 baris per interval)
- `.run/health_contract_last.json` (snapshot terakhir)

#### Watcher backend (doctor+smoke semi-otomatis)
Watcher akan memanggil `doctor-stack` saat backend berubah (hash kontrak/registry endpoint).

```bash
BACKEND=http://127.0.0.1:8008 make watch-backend-start
```

Jika ingin sekaligus menjalankan `smoke` setelah `doctor-stack`:

```bash
BACKEND=http://127.0.0.1:8008 WITH_SMOKE=1 make watch-backend-start
```

Stop:

```bash
make watch-backend-stop
```

---

## 6. Alur Operasi Harian (Runbook ringkas)
Urutan rekomendasi saat mulai bekerja:

1) Start sistem
- Canonical: `make stack-canonical`
- External backend: jalankan BE Anda, lalu start FE dengan `run-frontend-canonical` (base_url menunjuk BE Anda)

2) Jalankan doctor
- `make doctor-stack` (atau `BACKEND=... make doctor-stack`)

3) Buka UI
- `http://127.0.0.1:8050/?v=<timestamp>` untuk memastikan cache browser tidak menyimpan assets lama

4) Pantau banner readiness
- Jika “verified/live”: lanjut penggunaan normal
- Jika “blocked/degraded”: ikuti operator actions di banner, atau jalankan doctor ulang

5) Operasi tab sesuai kebutuhan (Monitoring → Optimization → Precooling → Reports)

6) Tutup sesi dengan menyimpan/ekspor hasil (Reports/Export) dan menyimpan artefak verifikasi bila dibutuhkan

### 6.1 Runbook ringkas untuk Demo (canonical 8008/8050)
Urutan yang disarankan:
1) Start canonical:
   - `make stack-canonical`
2) Refresh registry + verifikasi:
   - `BACKEND=http://127.0.0.1:8008 make doctor-stack`
3) Mulai observability (opsional tapi disarankan):
   - `make health-contract-start`
4) Buka UI (gunakan cache-buster):
   - `http://127.0.0.1:8050/?v=<timestamp>`

### 6.2 Runbook ringkas untuk Dev/Realtime (backend 8009)
Urutan yang disarankan:
1) Pastikan BE 8009 menyala
2) Start FE pointing ke 8009:
   - `ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 ECOAIMS_REQUIRE_CANONICAL_POLICY=false ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true make run-frontend-canonical`
3) Refresh registry:
   - `BACKEND=http://127.0.0.1:8009 make doctor-stack`
4) Nyalakan watcher (agar auto-run doctor saat BE berubah):
   - `BACKEND=http://127.0.0.1:8009 WITH_SMOKE=1 make watch-backend-start`

---

## 7. Panduan Per Tab/Fitur
Bagian ini menjelaskan fungsi, cara pakai, dan hal yang perlu diperhatikan.

### 7.1 Home
Fungsi:
- Ringkasan status integrasi (readiness, policy, registry, identity).
- Shortcut ke runbook/doctor.

Langkah pakai:
- Pastikan banner status “OK” sebelum melanjutkan ke tab lain.
- Jika ada mismatch, klik operator actions atau jalankan `make doctor-stack`.

### 7.2 Monitoring
Fungsi:
- Menampilkan kondisi energi real-time: Solar, Wind, Battery, Grid.
- Menampilkan tren/historis dan indikator kualitas data (trim/limit).

Hal penting:
- Jika backend tidak menyediakan data historis cukup, tab bisa “degraded” (indikator akan menjelaskan alasannya).
- Pada canonical lane, Monitoring akan diblokir jika kontrak/policy belum OK.

### 7.3 Forecasting
Fungsi:
- Proyeksi konsumsi/produksi berdasarkan periode.

Hal penting:
- Pastikan periode yang dipilih sesuai tujuan analisis (harian/jam).
- Jika backend memakai data dummy/placeholder, hasil forecasting perlu ditandai sebagai simulasi.

### 7.4 Optimization
Fungsi:
- Mengirim request optimisasi ke backend (`POST /optimize`) dan menampilkan distribusi energi serta rekomendasi.

Langkah pakai:
1) Pilih Priority (Renewable/Battery/Grid).
2) Atur Batas Penggunaan Kapasitas Baterai (%) dan Batas Daya Grid (kW).
3) Klik “Jalankan Simulasi Optimasi”.
4) Analisis:
   - Pie chart proporsi distribusi
   - Bar chart energi terpakai
   - Rekomendasi teks

Hal penting:
- Dropdown “Optimizer Backend (shared)” dipakai oleh Precooling/LAEOPF. Tidak otomatis mengubah hasil `POST /optimize` pada tab ini.
- Jika terjadi 500/0 server error:
  - Jalankan `BACKEND=... make doctor-backend-only`
  - Pastikan endpoint `/optimize` di backend menerima payload yang dikirim FE.

### 7.5 Precooling / LAEOPF
Fungsi:
- Status precooling hari ini (overview), schedule, simulasi skenario, KPI, alerts, audit.
- Menyediakan apply recommendation (bila backend menyediakan candidate ranking).

Cara membaca tampilan:
- Nilai “-” berarti field belum disediakan backend (bukan nol).
- “Candidate Ranking” kosong berarti backend tidak mengirim kandidat (insight belum tersedia) atau simulasi belum dijalankan.

Langkah pakai (skenario umum):
1) Pilih zone (jika tersedia).
2) Jalankan Simulate/Generate Candidates (jika tersedia di UI) untuk menghasilkan kandidat.
3) Pilih kandidat pada tabel ranking.
4) Klik Apply Recommendation untuk menerapkan (membutuhkan endpoint apply di backend).

Catatan penting:
- “Energy Source” pada overview adalah status yang dilaporkan backend (schedule aktif), bukan otomatis mengikuti dropdown UI.
- Jika Anda ingin angka advanced (thermal/latent/exergy), backend harus mengirim field tersebut.

#### 7.5.1 Precooling Selector (Contextual Bandit) — opsional
Tujuan: mengaktifkan “selector” untuk memilih kandidat precooling secara aman (safe bandit) serta menyediakan preview + audit.

Kontrol UI (default OFF):
- Toggle: **Enable Selector (Safe Bandit)**
- Dropdown: `selector_backend` = `grid` (default) / `milp` / `bandit`
- Advanced: `epsilon` (default 0.12), `min_candidates` (default 3)
- Tombol: **Preview Selector**

Cara pakai:
1) Jalankan **Run Simulation** atau **Generate Candidates** minimal 1x (agar payload simulate + `zone_id` tersedia).
2) Aktifkan toggle selector, pilih backend (mis. `bandit`), atur epsilon/min_candidates bila perlu.
3) Klik **Preview Selector**:
   - UI menampilkan ringkas kandidat terpilih + `selector_snapshot` (strategy/fallback/reason) serta `candidates_count` dan `feasible_count`.
   - Jika backend mengembalikan candidates summary (opsional), UI menampilkan top-N.
4) Jalankan **Run Simulation** saat selector ON:
   - FE mengirim field selector pada payload simulate: `selector_enabled=true`, `selector_backend`, `selector_epsilon`, `selector_min_candidates` (jika diisi).
   - Audit “Selector Audit” akan muncul bila backend menyertakan snapshot.

Audit trail:
- Pada backend baru, `selector_snapshot` biasanya muncul di `audit_trail` sebagai item:
  - `{"status":"selector_snapshot","selector_snapshot":{...}}`
- Jika snapshot tidak ada (selector OFF atau backend lama), UI tetap stabil dan menampilkan “(tidak tersedia)”.

### 7.6 Reports
Fungsi:
- Menampilkan impact precooling, trend, history, drilldown sesi, export.

Langkah pakai:
1) Klik Generate/Load Reports (sesuai UI).
2) Pastikan ringkasan dan grafik muncul.
3) Gunakan Export (CSV) bila data tersedia.
4) (Opsional) Klik **Backend Ops Watch** untuk melihat ringkasan monitoring backend (jika BE menyediakan `GET /ops/watch`).

Hal penting:
- Jika export gagal, periksa apakah data laporan sudah terbentuk (mis. `daily_data` atau dataset lain yang dibutuhkan).
- Jika backend tidak menyediakan endpoint reports tertentu, UI akan menampilkan “not supported/placeholder” pada external lane.

### 7.7 BMS
Fungsi:
- Visualisasi SOC/tegangan/arus/suhu serta kontrol charge/discharge (jika backend mendukung).

Hal penting:
- Jangan gunakan kontrol BMS pada sistem nyata tanpa prosedur keselamatan dan verifikasi akses/otorisasi.

#### 7.7.1 Hasil Optimizer RL (Battery Dispatch)
Di tab BMS terdapat panel “Hasil Optimizer RL (Battery Dispatch)” untuk menjalankan dispatch (backend `optimizer_backend="rl"`) dan menampilkan KPI + schedule.

Catatan:
- Tombol Run akan mengirim payload dispatch ke backend (serta polling dashboard dispatch bila tersedia).
- Field hasil yang ditampilkan dapat berbeda antar backend (canonical vs external).

#### 7.7.2 DRL Tuner (Safe Meta-Controller) — opsional
Tujuan: meminta backend memberikan rekomendasi parameter/weights yang **aman** (setelah safety shield) sebelum dispatch dijalankan.

Cara pakai:
1) Aktifkan toggle **Enable DRL Tuner** (default OFF).
2) Klik **Preview Suggestion** untuk melihat:
   - Suggested (raw) vs Effective (setelah shield)
   - Badge **FALLBACK** bila backend memakai fallback + reason (jika tersedia)
3) Klik **Run RL Dispatch**:
   - Jika tuner ON: FE akan mencoba memanggil tuner dulu dan menyertakan `effective_params` pada payload dispatch.
   - Jika tuner gagal: FE menampilkan alert dan tetap lanjut dispatch tanpa tuner (graceful degradation).

#### 7.7.3 DRL Policy Proposer + Safety Projection — opsional
Tujuan: melakukan preview “aksi policy” (proposed) dan “aksi aman setelah projection” (projected), lalu mengaktifkan policy saat run dispatch.

Cara pakai:
1) Aktifkan toggle **Enable Policy Proposer** (default OFF).
2) Isi context sederhana (SOC, demand_total_kwh, renewable_potential_kwh; tariff/emission opsional).
3) Klik **Preview Action** untuk melihat:
   - `proposed_action` vs `projected_action`
   - Badge **PROJECTION** bila `projection_applied=true` (jika tersedia)
   - Badge **FALLBACK** bila `fallback_used=true` + reason (jika tersedia)
4) Klik **Run RL Dispatch**:
   - Jika policy ON: FE menyetel `optimizer_config.policy_enabled=true` pada payload dispatch.
   - Jika preview gagal: tidak memblokir run dispatch.

### 7.8 Settings
Fungsi:
- Pengaturan global dan pengaturan spesifik modul (mis. Precooling settings).

Catatan penting:
- Status “NOT LOADED/NOT VALIDATED” berarti FE belum memuat baseline dari backend atau belum melakukan validasi.
- Gunakan urutan:
  - Load Current Settings → edit → Validate → Save Draft → Apply Active

---

## 8. Ekspor, Audit, dan Artefak Verifikasi
Jika Anda memerlukan bukti audit integrasi:

### 8.1 Crossrepo proof/evidence
```bash
make verify-canonical-crossrepo
```

Artefak (contoh):
- `output/verification/canonical_crossrepo_proof.json`
- `output/verification/canonical_crossrepo_evidence_bundle.json`

### 8.2 Checklist rilis/hardening
Gunakan:
- `docs/RELEASE_CHECKLIST.md`

---

## 9. Troubleshooting (Kasus umum & langkah pemulihan)
### 9.1 Port FE tidak bisa dipakai (8050 busy)
```bash
make stop-frontend
```

### 9.2 Banner “contract mismatch / blocked”
Langkah cepat:
1) Buka `http://127.0.0.1:8050/__runtime` → pastikan base_url benar.
2) Cek backend:
   - `GET /api/startup-info`
   - `GET /api/contracts/index`
3) Jalankan:
   - `make doctor-stack`
4) Jika backend menyediakan ops-watch: buka tab **Reports** → klik **Backend Ops Watch** untuk melihat ringkasan error backend (429/500) secara cepat.

Jika mismatch sering muncul saat backend berubah:
- jalankan logger: `make health-contract-start` lalu cek ringkasan: `make health-contract-report`
- jalankan watcher: `BACKEND=http://127.0.0.1:8008 WITH_SMOKE=1 make watch-backend-start`

### 9.3 Endpoint 404 di tab tertentu (external backend)
Itu berarti backend tidak menyediakan endpoint tersebut. Solusi:
- Pindah ke canonical (8008), atau
- Tambahkan endpoint tersebut di backend eksternal.

### 9.4 Error 0/500 pada Optimization/Precooling/Reports
Langkah cepat:
- `BACKEND=http://127.0.0.1:<port> make doctor-backend-only`
- Periksa log backend Anda dan validasi payload.

### 9.5 Monitoring “Comparison degraded” (histori tidak cukup)
Gejala:
- Di tab Monitoring muncul status seperti “DEGRADED: Data tidak cukup untuk comparison. Butuh minimal=12 …”

Penyebab umum:
- Backend hanya memiliki sedikit record historis (mis. `available_records_len=2`), sementara comparison butuh minimal record (mis. 12).

Langkah pemulihan (disarankan):
1) Buka endpoint diagnosa backend:
   - `GET /diag/monitoring`
2) Periksa:
   - `history.required_min_for_comparison`
   - `history.energy_data_records_count`
3) Jika backend Anda mendukung “seed via env” (development), set env di proses backend lalu restart backend:
   - `ECOAIMS_DEV_SEED_HISTORY=true`
   - `ECOAIMS_DEV_SEED_HISTORY_RECORDS=24` (atau minimal ≥ required_min)
   - `ECOAIMS_DEV_SEED_STREAM_ID=default`
   - `ECOAIMS_REQUIRED_MIN_FOR_COMPARISON=<required_min_for_comparison>`
4) Jika seed tidak tersedia, biarkan backend berjalan sampai histori terkumpul ≥ minimal, lalu refresh FE.

### 9.6 Login Gateway (Auth + Captcha)
Gejala umum:
- Akses `/` langsung masuk tanpa login.
- Captcha di halaman `/login` kosong/tidak muncul.
- Login gagal dengan error CSRF/captcha.

Diagnosis cepat:
```bash
curl -i http://127.0.0.1:8050/ | head -n 20
curl -i http://127.0.0.1:8050/api/auth/captcha | head -n 40
```

Interpretasi:
- Jika belum login, `/` harus `302` ke `/login?next=/`.
- `GET /api/auth/captcha` harus `200` dan biasanya mengirim `Set-Cookie` dari backend auth.

Penyebab paling sering:
- Browser masih menyimpan cookie session login (sehingga terlihat “tidak lewat login”). Gunakan incognito atau hapus cookie untuk `127.0.0.1:8050`.
- Backend auth belum hidup / base URL auth salah (proxy mode) sehingga `GET /api/auth/captcha` menjadi 404/503.

Catatan keamanan:
- Untuk produksi, disarankan mode `proxy` sehingga browser cukup bicara ke FE dan tidak perlu CORS lintas port.

---

## 10. Catatan Keamanan & Hardening
- Gunakan canonical lane untuk demo/rilis jika memungkinkan (fail-closed mengurangi risiko data salah).
- Jangan gunakan server dev untuk produksi tanpa WSGI server yang layak.
- Batasi CORS pada backend produksi (pada dev bisa longgar).
- Jangan log token/secret ke console/log.
- Jika mengaktifkan aksi apply/control (Precooling apply, BMS control), pastikan ada mekanisme otorisasi di backend.
- Jika mengaktifkan gateway login:
  - Jalankan FE di belakang HTTPS reverse proxy, set `ECOAIMS_FORCE_HTTPS=true` dan `ECOAIMS_SESSION_COOKIE_SECURE=true`.
  - Set `ECOAIMS_SESSION_SECRET` agar session konsisten setelah restart.
  - Jangan expose port backend auth ke publik; cukup FE yang publik, BE di jaringan internal.

---

## 11. Lampiran: Perintah Make & Environment Variables
### 11.1 Perintah Make yang sering dipakai
- `make check` / `make check-all`
- `make stack-canonical`
- `make run-frontend-canonical`
- `make doctor-stack`
- `make smoke` / `make smoke-browser`
- `make mismatch-check` (debug kontrak endpoint)
- `make clean-run` (hapus `.run/`)
- `make health-contract-start` / `make health-contract-report` / `make health-contract-stop`
- `make watch-backend-start` / `make watch-backend-stop`
- `make gen-always-on` (generate file service always-on)

### 11.2 Env vars penting
- `ECOAIMS_FE_REPO`, `ECOAIMS_BE_REPO`: path repo untuk mode “jalan dari mana saja”
- `ECOAIMS_API_BASE_URL_CANONICAL`: base_url backend yang akan dipakai saat start FE via Makefile
- `ECOAIMS_REQUIRE_CANONICAL_POLICY`:
  - true: strict canonical (fail-closed)
  - false: lebih toleran untuk backend eksternal
- `ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO`: izinkan startup-info minimal (untuk backend eksternal)
- `ECOAIMS_STRICT_CONTRACT_VERSION`: paksa contract_version harus match (opsional)
- `ECOAIMS_DOCTOR_STRICT`: strict/lenient saat doctor backend-only
- `ECOAIMS_HTTP_TRACE_HEADERS`: aktifkan header traceability FE→BE (true/false)
- `ECOAIMS_FE_BUILD_ID`, `ECOAIMS_FE_VERSION`, `ECOAIMS_FE_SESSION_ID`: identitas traceability FE
- `FE_HOST`, `FE_PORT`, `BACKEND`: override target untuk doctor/FE
- Monitoring (development seed history):
  - `ECOAIMS_DEV_SEED_HISTORY`, `ECOAIMS_DEV_SEED_HISTORY_RECORDS`, `ECOAIMS_DEV_SEED_STREAM_ID`, `ECOAIMS_REQUIRED_MIN_FOR_COMPARISON`
- Auth gateway (FE):
  - `ECOAIMS_AUTH_ENABLED` (true/false)
  - `ECOAIMS_AUTH_MODE` (disarankan: `proxy`)
  - `ECOAIMS_AUTH_BACKEND_BASE_URL`
  - `ECOAIMS_FORCE_HTTPS` (true/false)
  - `ECOAIMS_SESSION_COOKIE_SECURE` (true/false)
  - `ECOAIMS_SESSION_SECRET`
