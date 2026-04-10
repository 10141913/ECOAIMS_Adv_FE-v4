# Catatan Sesi (FE) — 2026-03-26
Repository: ECOAIMS_Adv_FE v-4  
Fokus: Hardening integrasi FE↔BE, Always-on, UI reliability, kontrak runtime, observability

## 1) Tujuan Awal dan Arah Perubahan
Target sesi adalah membuat sistem FE lebih stabil dan “research/ops-grade” dengan:
- Integrasi FE↔BE yang lebih dapat ditelusuri (trace headers).
- Registry/contract yang lebih deterministik (refresh & mismatch visibility).
- UI yang tahan terhadap kegagalan backend (graceful degradation; tidak blank).
- Caching UI yang nyaman untuk operator/peneliti.
- E2E smoke test berbasis Playwright untuk regresi antar-tab.
- Dokumentasi (README + buku manual) selalu mengikuti perubahan.

## 2) Pekerjaan yang Selesai di FE (Ringkas)
### 2.1 Trace Headers (Default ON)
Tujuan: setiap request FE mengirim identitas build/session ke BE sehingga debugging lintas sistem mudah.
- Konsep: header seperti `X-ECOAIMS-FE-BUILD` dan `X-ECOAIMS-FE-SESSION`.
- Penyesuaian test: saat unit test, trace headers dimatikan agar mock `requests.get` tidak gagal.

### 2.2 Registry Refresh (Operasional)
Tujuan: saat kontrak backend berubah, FE bisa memaksa refresh registry tanpa restart.
- Ditambahkan tombol “Refresh Registry” di tab About untuk membersihkan cache registry FE.
- Ditambahkan tampilan runtime info di tab About:
  - Active Base URL
  - FE Build ID
  - Latest Contract Hash

### 2.3 Dokumentasi Manual (dipindahkan ke About)
Tujuan: mengurangi titik kegagalan runtime (hindari download PDF server-side) dan merapikan UX.
- Link manual dipindahkan ke tab About dengan opsi “Cetak ke PDF (browser)”.
- Tombol “Dokumentasi Lengkap” di Help/FAQ dibersihkan.

### 2.4 Graceful Degradation (Optimization & Precooling)
Tujuan: jika BE rate-limited / timeout / error, UI tidak blank; tampil banner “Simulasi Gagal…”.
- Callback Optimization dan Precooling dibungkus try/except untuk jalur error.
- Output pada jalur error diset aman (figure placeholder + banner).

### 2.5 Browser Caching (persistence session)
Tujuan: perpindahan tab cepat dan input tidak reset.
- Dropdown/slider/input utama pada Optimization/Precooling/Forecasting/Reports dibuat persistent (`persistence_type='session'`).

### 2.6 E2E Smoke Test (Playwright)
Tujuan: punya bot yang mengeklik semua tab untuk memastikan FE+BE sehat sebelum rilis.
- `scripts/smoke_browser.py` dipakai sebagai runner Playwright untuk traversal tab.
- `make smoke-browser` menjadi jalur cepat verifikasi UI.

## 3) Insiden dan Root Cause (Pembelajaran)
### 3.1 Monitoring gauges hilang saat backend tidak siap
Gejala: pada tab Monitoring, visualisasi Solar/Wind/Grid/Biofuel kadang tidak muncul.
Root cause: callback Monitoring pada jalur “backend gagal/menunggu” mengembalikan jumlah output yang tidak sesuai deklarasi Dash, sehingga callback crash dan komponen tidak ter-render.
Perbaikan: return jalur error diselaraskan agar konsisten dengan jumlah output yang didaftarkan.
Pelajaran:
- Error-path harus diperlakukan sama penting dengan happy-path.
- Smoke test perlu memverifikasi degraded path (bukan hanya “tab terbuka”).

### 3.2 Precooling: `runtime_endpoint_contract_mismatch` “no_fallback_validator”
Gejala: zone discovery selalu menampilkan mismatch: `no_fallback_validator:GET /api/precooling/zones`.
Root cause: registry runtime contracts FE tidak punya fallback validator untuk endpoint tersebut.
Perbaikan:
- Menambahkan validator minimal untuk `GET /api/precooling/zones`.
- Mengaitkan validator itu ke mapping registry.
Pelajaran:
- Jika registry index/manifest belum lengkap atau bergeser, fallback validator yang “minimal & transparan” mencegah UI terhenti total.

### 3.3 Monitoring “Comparison degraded” walau demo dijalankan
Gejala: `DEGRADED: Data tidak cukup untuk comparison. Butuh minimal=12 … records_len=1`.
Root cause: ini bukan bug FE. Backend memang hanya memiliki 1 record historis; FE hanya menampilkan status degraded sesuai `/diag/monitoring`.
Pelajaran:
- FE harus “jujur”: bedakan jelas masalah readiness data BE vs bug FE.
- Untuk demo lane, BE harus menyediakan seed history ≥ 12.

### 3.4 Bug “NoneX” (contoh `None_v2`, `None2`) yang berpotensi crash di error-path
Gejala: potensi NameError pada error-path Precooling API wrapper.
Perbaikan minimal:
- `None_v2` diganti ke `err_v2` pada `get_status`.
- `None2` diganti ke `err2` pada jalur fallback apply.
Pelajaran:
- Variable typo semacam ini jarang tertangkap jika jalur error tidak diuji.
- Perlu lint guard agar pola “NoneX” tidak muncul lagi.

### 3.5 Audit “NoneX” dan Lint Guard
Hasil audit: setelah perbaikan, tidak ada pola `NoneX` tersisa di source code FE.
Tindakan: menambahkan lint guard di Makefile agar `make lint` gagal bila pola `None_v2/None2/None_foo` muncul.
Pelajaran:
- Guard sederhana di pipeline mencegah regresi kelas “typo error-path” yang mahal untuk debugging.

## 4) Observability: Ops Watch dari Backend di Tab Reports
Tujuan: operator bisa membuka ringkasan monitoring BE langsung dari UI FE (tanpa terminal).

Implementasi FE:
- Tombol “Backend Ops Watch” pada tab Reports menampilkan modal yang memuat output ops-watch BE melalui HTTP.
- FE mencoba endpoint kandidat (minimal `/ops/watch`) dan menampilkan plain text dalam `html.Pre`.
- (Opsional) dukungan download report bisa ditambahkan jika diperlukan (mis. via `dcc.Download`), dengan tetap tidak membaca file BE secara langsung.

Pelajaran:
- FE tidak bisa “membaca `.run/ops_watch.log`” di mesin BE; solusinya adalah endpoint BE `GET /ops/watch` yang mengembalikan ringkasan.

## 5) Always-on (launchd) dan Realita Operasional
Skrip generator service (`scripts/gen_always_on_services.py`) dijalankan untuk menghasilkan file `.plist` (launchd) untuk macOS.
Catatan operasional:
- Always-on baru aktif jika file `.plist` dipindahkan ke `~/Library/LaunchAgents/` dan di-load via `launchctl load -w …`.
- Jika FE/BE masih dijalankan manual stack, maka proses mungkin “aktif” tetapi bukan “always-on” (tidak dikelola launchd).
- Jangan mencampur mode manual vs launchd pada port yang sama untuk menghindari port conflict/respawn.

## 6) Checklist Verifikasi yang Dipakai
Setiap perubahan signifikan divalidasi dengan:
- `make check` (unit test + audit callbacks + smoke stack)
- `make smoke-browser` (Playwright E2E tab traversal)

Prinsip:
- Jangan menyatakan fitur selesai tanpa minimal `make check` lulus.

## 7) Rencana Aman (yang disepakati sebagai urutan risiko minimum)
Prioritas FE+Integrasi yang paling aman (untuk dieksekusi bertahap):
1) Transparansi mode/lane di About (display-only; low risk)
2) Audit error-path callback + tests minimal (anti blank; medium risk, high impact)
3) Fallback validator minimal & transparan untuk endpoint yang dipakai UI (medium risk; perlu guard)
4) Auto refresh registry 1x deterministik (low–medium risk; harus anti-loop)
5) Playwright degraded-path assertions (test-only; menjaga regresi)
6) Update docs/SOP (low risk; kurangi human error)

## 8) Daftar File yang Relevan (untuk navigasi)
FE Core:
- ecoaims_frontend/app.py
- ecoaims_frontend/layouts/main_layout.py
- ecoaims_frontend/layouts/about_layout.py
- ecoaims_frontend/callbacks/about_callbacks.py
- ecoaims_frontend/callbacks/main_callbacks.py
- ecoaims_frontend/callbacks/optimization_callbacks.py
- ecoaims_frontend/callbacks/precooling_callbacks.py

Services & Contracts:
- ecoaims_frontend/services/http_trace.py
- ecoaims_frontend/services/contract_registry.py
- ecoaims_frontend/services/runtime_contracts.py
- ecoaims_frontend/services/precooling_api.py
- ecoaims_frontend/services/reports_api.py

Testing & Automation:
- scripts/smoke_browser.py
- scripts/smoke_browser_stack.py
- ecoaims_frontend/tests/

Documentation:
- ecoaims_frontend/README.md
- books/MANUAL_BOOK_ID.md
- books/MANUAL_BOOK_RESEARCH_ID.md

## 9) “Lessons Learned” (Ringkas untuk pembelajaran)
- Lane discipline (base_url/port/mode) harus tegas, atau debugging jadi ilusi.
- Error-path yang tidak diuji akan menjadi sumber kerusakan UI yang tampak “random”.
- Kontrak runtime perlu fallback minimal, tetapi harus transparan agar tidak menutupi data salah.
- Observability paling efektif adalah yang muncul langsung di UI (Reports/About), bukan hanya di terminal.
- Pipeline guard kecil (seperti lint guard NoneX) bisa mencegah bug kelas “typo” yang mahal.
