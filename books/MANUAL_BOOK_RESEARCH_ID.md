# Manual Book untuk Peneliti — ECO-AIMS (FE↔BE)

Dokumen ini berfokus pada kebutuhan penelitian: skenario eksperimen, pencatatan parameter, prosedur pengujian berulang, dan template laporan hasil uji. Manual ini melengkapi `books/MANUAL_BOOK_ID.md` (manual operator).

## 0. Tujuan Penelitian yang Disarankan
Sebelum eksperimen, tetapkan tujuan yang terukur. Contoh:
- **Validasi integrasi**: memastikan FE menampilkan data yang benar, konsisten dengan BE, dan tidak crash pada kondisi normal/error.
- **Evaluasi algoritma**:
  - Optimization: dampak prioritas (renewable/battery/grid) pada bauran energi, unmet demand, dan pemakaian grid.
  - Precooling/LAEOPF: dampak setpoint & time window pada comfort compliance, peak reduction, biaya, dan CO2.
- **Robustness**: perilaku sistem saat backend mengalami downtime, kontrak berubah, data tidak lengkap, atau latensi tinggi.

---

## 1. Definisi “Lane” untuk Eksperimen
Selalu tulis lane yang digunakan pada setiap hasil uji.

### 1.1 Canonical Lane (fail-closed)
Dipakai saat Anda ingin kontrol ketat dan hasil paling dapat dibandingkan antar-run.

- Start:

```bash
NO_OPEN=1 make stack-canonical
```

Tracing (opsional, disarankan untuk traceability):

```bash
export ECOAIMS_HTTP_TRACE_HEADERS=true
export ECOAIMS_FE_BUILD_ID="demo-$(date +%Y%m%d-%H%M%S)"
export ECOAIMS_FE_VERSION="v2"
```

- Sinyal sukses:
  - Banner “Canonical integration verified”
  - `http://127.0.0.1:8050/__runtime` menunjukkan base_url=8008

### 1.2 External/Devtools Lane (kompatibilitas)
Dipakai saat BE bukan canonical (mis. 8009) atau Anda menguji BE varian tertentu.

```bash
ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 \
ECOAIMS_REQUIRE_CANONICAL_POLICY=false \
ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true \
make run-frontend-canonical
```

Alternatif (jalankan FE saja dari repo FE, jika backend sudah hidup):

```bash
ECOAIMS_API_BASE_URL=http://127.0.0.1:8009 \
ECOAIMS_DASH_HOST=127.0.0.1 \
ECOAIMS_DASH_PORT=8050 \
./ecoaims_frontend_env/bin/python -m ecoaims_frontend.app
```

Catatan:
- Pada lane ini, sebagian tab bisa “placeholder/not supported” jika BE tidak menyediakan endpoint tertentu.
- Lane ini tetap berguna untuk menguji UI robustness dan evolusi kontrak.

---

## 2. Protokol Eksperimen (Disarankan)
Gunakan urutan berikut untuk setiap sesi eksperimen agar hasil konsisten.

### 2.1 Reset kondisi awal
- Matikan FE yang berjalan:

```bash
make stop-frontend
```

- Jika Anda menjalankan canonical stack, bersihkan log run lokal:

```bash
make clean-run
```

### 2.2 Start sistem (pilih lane)
- Canonical: `make stack-canonical`
- External: jalankan BE Anda, lalu start FE seperti di bagian 1.2
- **Daemon (Always-On)**: Jika Anda ingin sistem berjalan otomatis di *background* untuk eksperimen jangka panjang tanpa terganggu *terminal close*:
  ```bash
  export ECOAIMS_FE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_FE v-4"
  export ECOAIMS_BE_REPO="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
  ./ecoaims_frontend_env/bin/python scripts/gen_always_on_services.py --mode canonical
  cp ops/generated/launchd/*.plist ~/Library/LaunchAgents/
  launchctl load -w ~/Library/LaunchAgents/com.ecoaims.backend.8008.plist
  launchctl load -w ~/Library/LaunchAgents/com.ecoaims.frontend.8050.plist
  ```
  Catatan: untuk backend eksternal (mis. 8009), gunakan `--mode external` sehingga label menjadi `com.ecoaims.backend.8009` dan FE tetap di 8050.

### 2.2.1 Auth Gateway (Login + Captcha) untuk sesi eksperimen
Jika FE Anda mengaktifkan gateway login, pastikan Anda mencatat konfigurasi auth pada setiap run agar hasil eksperimen dapat direplikasi.

Mode yang disarankan untuk server adalah `proxy` (FE meneruskan auth ke BE):
- FE endpoint (dipanggil browser):
  - `GET /api/auth/captcha`
  - `POST /api/auth/login`
- BE endpoint (dipanggil FE):
  - `GET /api/auth/captcha`
  - `POST /api/auth/login`

Env vars yang dicatat pada metadata run:
- `ECOAIMS_AUTH_ENABLED`
- `ECOAIMS_AUTH_MODE` (disarankan: `proxy`)
- `ECOAIMS_AUTH_BACKEND_BASE_URL`
- `ECOAIMS_FORCE_HTTPS` dan `ECOAIMS_SESSION_COOKIE_SECURE` (jika behind TLS)

Smoke check cepat (tanpa browser):
```bash
curl -i http://127.0.0.1:8050/ | head -n 20
curl -i http://127.0.0.1:8050/api/auth/captcha | head -n 40
```

Catatan untuk eksperimen berulang:
- Jika UI terasa “langsung masuk” tanpa login, itu biasanya karena cookie session browser masih tersimpan. Gunakan incognito atau hapus cookie domain FE untuk memastikan run dimulai dari kondisi bersih.
- Jika captcha tidak muncul, cek dulu respons `GET /api/auth/captcha` (404/503 biasanya berarti BE auth belum hidup atau base_url auth salah).

### 2.3 Verifikasi awal (wajib dicatat)
Jalankan:

```bash
BACKEND=http://127.0.0.1:8008 make doctor-stack
```

atau untuk external:

```bash
BACKEND=http://127.0.0.1:8009 make doctor-stack
```

Catat hasil:
- `base_url`
- `contract_version`, `contract_manifest_hash`
- `REGISTRY_LOADED`, `CANONICAL_INTEGRATION_OK`, `VERIFICATION_OK` (banner home)
- daftar endpoint checked di doctor report (jika relevan)

### 2.4 Snapshot kondisi sistem (wajib)
Catat output:
- `GET /__runtime` (FE)
- `GET /api/startup-info` (BE)
- `GET /api/contracts/index` (BE)

### 2.5 Logging kontrak (disarankan untuk traceability)
Untuk penelitian, simpan log integrasi per run agar bisa membuktikan “kapan backend berubah” dan “kapan FE di-refresh”.

Opsi A (mudah): gunakan output default `.run/`:

```bash
make health-contract-start
make health-contract-report
```

Opsi B (lebih rapi): simpan log ke folder eksperimen (jalankan script langsung):

```bash
./ecoaims_frontend_env/bin/python scripts/health_contract_dashboard.py --out "research_runs/<RUN_ID>/health_contract.jsonl" --state "research_runs/<RUN_ID>/health_contract_last.json"
```

Ringkas report dari log eksperimen:

```bash
./ecoaims_frontend_env/bin/python scripts/health_contract_report.py --path "research_runs/<RUN_ID>/health_contract.jsonl"
```

### 2.6 Watcher backend (opsional)
Jika Anda sering restart/mengubah backend selama eksperimen, watcher bisa mengurangi risiko FE memakai registry lama.

```bash
BACKEND=http://127.0.0.1:8008 WITH_SMOKE=1 make watch-backend-start
```

Stop:

```bash
make watch-backend-stop
```

### 2.7 Ops Watch (Backend) dari UI FE (disarankan untuk eksperimen)
Jika BE menyediakan endpoint `GET /ops/watch`, FE dapat menampilkan ringkasan monitoring backend langsung dari UI.

Prasyarat (di BE):
- Endpoint: `http://127.0.0.1:8008/ops/watch?tail=200&minutes=60` (plain text).

Cara pakai (di FE):
1) Buka tab **Reports** → klik tombol **Backend Ops Watch**.
2) Klik **Refresh** untuk memuat data terbaru.
3) Salin konten report ke folder eksperimen (mis. `research_runs/<RUN_ID>/ops_watch.txt`) sebagai artefak observability.

### 2.8 End-to-End Test (E2E) dengan Playwright
Sebelum rilis eksperimen baru, jalankan automation bot untuk mengeklik seluruh tab (dari Monitoring hingga About) untuk memverifikasi kesehatan sistem (FE + BE):
```bash
# Menjalankan bot (headless browser)
make smoke-browser
```

### 2.9 Browser Caching & Graceful Degradation
- **Browser Caching:** UI secara otomatis menyimpan pilihan input/dropdown ke `session` browser. Ini membuat perpindahan antar tab jauh lebih cepat karena tidak perlu me-request data yang sama ke backend berkali-kali.
- **Graceful Degradation:** Jika API Backend *timeout* karena algoritma *optimization* atau *precooling* yang terlalu berat, tab UI tidak akan *crash*, melainkan memunculkan status *banner* error yang jelas.

---

## 3. Instrumen Pencatatan (Apa yang harus direkam)
Disarankan membuat folder per eksperimen, misalnya:

```text
research_runs/
  2026-03-25_exp01_canonical/
    metadata.json
    doctor_report.json
    screenshots/
    exports/
    notes.md
```

### 3.1 Metadata minimal yang wajib
Gunakan template JSON berikut pada setiap run:

```json
{
  "run_id": "2026-03-25_exp01_canonical",
  "date": "2026-03-25",
  "lane": "canonical",
  "fe_url": "http://127.0.0.1:8050/",
  "be_base_url": "http://127.0.0.1:8008",
  "traceability": {
    "http_trace_headers": true,
    "fe_build_id": null,
    "fe_version": null
  },
  "observability": {
    "health_contract_log_path": null,
    "health_contract_last_path": null
  },
  "fe_runtime": {
    "pid": null,
    "started_at": null
  },
  "be_startup_info": {
    "schema_version": null,
    "contract_version": null,
    "contract_manifest_id": null,
    "contract_manifest_hash": null
  },
  "verification": {
    "registry_loaded": null,
    "canonical_integration_ok": null,
    "backend_identity_ok": null,
    "verification_ok": null
  },
  "notes": ""
}
```

### 3.2 Artefak yang disarankan
- Screenshot tab utama:
  - Home (banner integrasi)
  - Monitoring (grafik + indikator trim)
  - Optimization (pie/bar + rekomendasi)
  - Precooling/LAEOPF (overview + KPI + scenario)
  - Reports (impact + trend + export)
- Export:
  - CSV reports (jika tersedia)
  - Bukti audit (jika canonical crossrepo)
- DRL (jika diuji):
  - Screenshot + copy raw output **DRL Policy Proposer** (proposed_action vs projected_action, projection/fallback badge)
  - Screenshot + copy raw output **DRL Tuner (Safe)** (suggested vs effective + meta)
  - Raw response dispatch + ringkasan **policy_snapshot** (bila backend mengirimkan)
- Precooling Selector (jika diuji):
  - Screenshot + copy raw output **Preview Selector** (`selector_snapshot`, selected_candidate, candidates_count/feasible_count)
  - Screenshot panel **Selector Audit** (snapshot dari `audit_trail` item `status="selector_snapshot"`)

---

## 4. Skenario Eksperimen yang Direkomendasikan
Skenario di bawah dirancang agar menguji perilaku sistem dari sisi UI dan integrasi BE.

### 4.1 Skenario A — Validasi Integrasi Canonical (Baseline)
Tujuan: memastikan sistem lulus verifikasi ketat dan semua tab “live”.

Langkah:
1) `make stack-canonical`
2) `make doctor-stack`
3) (Opsional) aktifkan tracing FE→BE dan restart FE agar header berlaku
4) Buka FE, pastikan banner “verified”
5) Buka tab:
   - Monitoring: cek data energy + comparison
   - Optimization: jalankan simulasi dengan prioritas berbeda
   - Precooling: cek status/schedule, jalankan simulate (jika tersedia)
   - Reports: cek impact, history, export
6) Jalankan: `make smoke-browser`

Output yang dicatat:
- screenshot per tab + hasil smoke-browser (PASS/FAIL)
- `output/verification/` bila Anda juga jalankan crossrepo proof

### 4.2 Skenario B — Robustness saat Backend Down
Tujuan: menguji handling error dan pesan operator actions.

Langkah:
1) Start FE normal (canonical/external)
2) Matikan backend (stop uvicorn/port)
3) Refresh FE:
   - Pastikan banner “waiting / backend down” muncul (bukan crash)
4) Nyalakan backend lagi
5) Jalankan `make doctor-stack` untuk recovery

Catat:
- waktu recovery
- apakah UI kembali normal tanpa restart FE

Catatan tambahan (Monitoring comparison):
- Jika tab Monitoring menampilkan “Comparison degraded” karena histori belum cukup (mis. min=12 tapi record=2), itu bukan crash UI. Untuk eksperimen yang membutuhkan comparison, seed/generate history di backend (development) lalu restart backend (lihat env `ECOAIMS_DEV_SEED_HISTORY*` di halaman instruksi Monitoring History di FE).

### 4.3 Skenario C — Evolusi Kontrak (Registry berubah)
Tujuan: memastikan FE bereaksi benar saat manifest hash berubah.

Langkah:
1) Jalankan FE mengarah ke backend (8009/varian) dan pastikan registry_loaded true
2) Ubah BE (tambah endpoint/ubah contract hash) lalu restart BE
3) Jalankan `make doctor-stack` untuk refresh registry FE
4) Pastikan banner mismatch hilang dan tab kembali normal

Catat:
- sebelum/sesudah `contract_manifest_hash`
- apakah endpoint baru muncul “not supported” atau “live”

### 4.4 Skenario D — Optimization Sensitivity Study (Parameter Sweep)
Tujuan: mengukur sensitivitas output distribusi energi terhadap parameter.

Variabel bebas (contoh):
- priority: renewable / battery / grid
- battery_capacity_usage: 20, 50, 80 (%)
- grid_limit: 50, 100, 150 (kW)

Prosedur:
1) Untuk setiap kombinasi parameter:
   - Jalankan simulasi
   - Simpan output (pie/bar + rekomendasi + snapshot backend)
2) Buat tabel ringkasan:
   - solar_kW, wind_kW, battery_kW, grid_kW, unmet_kW (jika tersedia)

Catatan:
- Jika output tidak berubah, periksa apakah backend memakai input yang sama (atau mode “placeholder”).

### 4.5 Skenario E — Precooling/LAEOPF Comparative Study
Tujuan: membandingkan outcome skenario precooling.

Variabel bebas (contoh):
- zone: zone_a/zone_b/zone_c
- time window: earliest/latest start
- target T & RH range
- objective weights: comfort/cost/co2/battery_health
- optimizer backend (untuk precooling): grid/mpc/cem (jika BE mendukung)

Metrik hasil (contoh):
- comfort_compliance (%)
- peak_reduction_kw
- energy_saving_kwh
- cost_saving (mata uang)
- co2_reduction_kg

Catatan:
- Jika panel banyak “-” atau candidate ranking kosong, artinya backend belum mengirim insight/advanced fields.

### 4.6 Skenario F — DRL Policy Proposer + Safety Projection (Preview vs Apply)
Tujuan: membuktikan bahwa “aksi policy” yang diusulkan (proposed) dapat berbeda dari aksi aman setelah safety projection (projected), serta memastikan dispatch tetap berjalan ketika policy diaktifkan.

Prasyarat:
- Gunakan tab **BMS → Hasil Optimizer RL (Battery Dispatch)**.
- Policy proposer di UI default OFF (tidak mengubah perilaku bila tidak diaktifkan).

Langkah:
1) Aktifkan toggle **Enable Policy Proposer**.
2) Isi context sederhana:
   - SOC
   - demand_total_kwh
   - renewable_potential_kwh
   - tariff/emission (opsional)
3) Klik **Preview Action**:
   - Catat `proposed_action` dan `projected_action`.
   - Catat `projection_applied` (badge PROJECTION) dan `fallback_used` + reason (badge FALLBACK) bila ada.
4) Jalankan **Run RL Dispatch** saat policy ON:
   - Pastikan payload dispatch menyertakan flag policy (di sisi FE: `optimizer_config.policy_enabled=true`).
   - Catat hasil dispatch dan cari `policy_snapshot` (jika backend mengirimkan) untuk provenance.

Kriteria sukses (untuk laporan penelitian):
- UI menampilkan proposed vs projected secara jelas.
- Dispatch tetap berjalan ketika policy ON.
- Jika backend mengirim `policy_snapshot`, provenance tertampil tanpa crash; jika tidak ada, UI tetap stabil.

### 4.7 Skenario G — DRL Tuner (Safe) sebagai Override Params
Tujuan: membuktikan FE dapat meminta parameter/weights efektif dari backend (setelah shield) dan tetap melakukan dispatch walau tuner gagal (graceful degradation).

Langkah:
1) Aktifkan toggle **Enable DRL Tuner**.
2) Klik **Preview Suggestion**:
   - Catat suggested vs effective + meta (fallback).
3) Jalankan **Run RL Dispatch** saat tuner ON:
   - Pastikan FE mencoba menyertakan `effective_params` pada payload dispatch.
4) Uji kegagalan tuner (opsional):
   - Matikan endpoint tuner / putuskan koneksi.
   - Pastikan UI menampilkan alert dan dispatch tetap berjalan tanpa tuner.

### 4.8 Skenario H — Precooling Selector (Contextual Bandit) Preview + Audit
Tujuan: membuktikan FE dapat memanggil preview selector dan menampilkan provenance selector dari hasil simulate melalui `audit_trail`.

Prasyarat:
- Gunakan tab **Precooling/LAEOPF**.
- Selector di UI default OFF (tidak mengubah perilaku bila tidak diaktifkan).

Langkah:
1) Jalankan **Run Simulation** atau **Generate Candidates** minimal 1x untuk zone yang dipilih.
2) Aktifkan toggle **Enable Selector (Safe Bandit)**.
3) Pilih `selector_backend` (grid/milp/bandit), atur `epsilon` dan `min_candidates` bila diperlukan.
4) Klik **Preview Selector**:
   - Catat `selector_snapshot.strategy` serta `fallback_used` + `fallback_reason` bila ada.
   - Catat `candidates_count` dan `feasible_count`.
   - Jika `return_candidates=true`, simpan top-N candidates summary sebagai artefak.
5) Jalankan **Run Simulation** saat selector ON:
   - Pastikan payload simulate menyertakan `selector_enabled`, `selector_backend`, `selector_epsilon`, `selector_min_candidates`.
6) Setelah simulate selesai, buka panel audit:
   - Pastikan ada item `audit_trail` dengan `status="selector_snapshot"` dan snapshot ditampilkan di “Selector Audit”.

Kriteria sukses (untuk laporan penelitian):
- Preview selector tampil konsisten (selected candidate + snapshot + counts).
- Audit selector tampil dari `audit_trail` tanpa crash; jika snapshot tidak ada, UI tetap stabil.

---

## 5. Template Laporan Hasil Uji (Markdown)
Gunakan template berikut untuk setiap eksperimen.

### 5.1 Template Ringkas

```markdown
# Laporan Uji ECO-AIMS — <RUN_ID>

## 1) Ringkasan
- Tanggal:
- Lane: canonical / external
- FE URL:
- BE base_url:
- Tujuan uji:

## 2) Setup
- Commit/versi FE:
- Commit/versi BE:
- Env vars penting:
- Backend contract_version:
- contract_manifest_hash:

## 3) Prosedur
1.
2.
3.

## 4) Hasil
### 4.1 Home/Readiness
- Banner:
- Doctor report: PASS/FAIL (lampiran)

### 4.2 Monitoring
- Observasi:
- Screenshot:

### 4.3 Optimization
- Parameter:
- Output:
- Screenshot:

### 4.4 Precooling/LAEOPF
- Zone:
- Skenario:
- KPI:
- Screenshot:

### 4.5 Reports
- Impact summary:
- Export CSV: sukses/gagal

## 5) Robustness (jika diuji)
- Backend down → hasil:
- Kontrak berubah → hasil:

## 6) Analisis & Kesimpulan
- Temuan utama:
- Risiko/limitasi:

## 7) Backlog/Perbaikan Lanjutan
- FE:
- BE:

## Lampiran
- metadata.json
- startup-info.json
- contracts-index.json
- screenshot(s)
```

### 5.2 Template Tabel Parameter Sweep (Optimization)

```markdown
## Tabel Hasil Optimization (Parameter Sweep)

| priority | battery_usage_% | grid_limit_kw | solar_kw | wind_kw | battery_kw | grid_kw | unmet_kw | catatan |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| renewable | 20 | 50 |  |  |  |  |  |  |
| renewable | 50 | 50 |  |  |  |  |  |  |
```

---

## 6. Verifikasi & Hardening untuk Peneliti
### 6.1 Release/hardening checklist
Gunakan:
- `docs/RELEASE_CHECKLIST.md`
- `make release-check`

### 6.2 Bukti audit (opsional, untuk laporan formal)
Jika penelitian membutuhkan bukti integrasi lintas repo:

```bash
make verify-canonical-crossrepo
```

Artefak ada di `output/verification/`.

---

## 7. Tips Interpretasi Hasil (Agar tidak salah simpulan)
- **Nilai “-”** berarti field tidak disediakan backend, bukan nol.
- **Nilai 0** berarti backend mengirim angka 0 (bisa valid atau placeholder).
- Jika hasil tidak berubah pada penggantian parameter:
  - Cek apakah backend benar-benar memakai input tersebut (bisa saja backend memakai data state tetap).
  - Cek apakah backend sedang “fallback/placeholder mode”.
- Untuk banding antar-run, gunakan canonical lane jika memungkinkan.
