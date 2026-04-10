## Load Testing (FE+BE)

Dokumen ini berfokus pada pengujian beban untuk:
- ramp-up concurrency
- distribusi status code (khususnya rasio 429)
- latency (p50/p95/p99/max)

### Prasyarat

- Backend dan Frontend berjalan (lokal atau environment staging).
- Python environment FE aktif (`./ecoaims_frontend_env/bin/python`).

### 1) Dash Callback Load Loop (tanpa sentuh BE)

Ini men-stress endpoint Dash `/_dash-update-component` untuk Monitoring/Comparison dan cocok untuk uji beban hingga 50k–1M iterasi.

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=500000
export ECOAIMS_SMOKE_DASH_LOOP_TARGETS=monitoring,comparison
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
export ECOAIMS_SMOKE_DASH_LOOP_PROGRESS_EVERY=10000
python scripts/smoke_runtime.py
```

Interpretasi cepat:
- `p95_ms`/`p99_ms` naik tajam → indikasi bottleneck.
- `peak_rss_kb` naik terus sepanjang run → indikasi memory leak (atau cache tak terkendali).

### 2) HTTP Load Test untuk Endpoint Kritikal (rate-limiting / 429)

Gunakan runner HTTP untuk memukul endpoint tertentu dengan ramp-up dan mengukur:
- p95/p99 latency
- 429 ratio
- error ratio (>=400 selain 429)

Contoh uji `GET /api/contracts/index` dan `POST /optimize`:

```bash
export ECOAIMS_LOAD_BASE_URL=http://127.0.0.1:8008
export ECOAIMS_LOAD_CONCURRENCY=50
export ECOAIMS_LOAD_TOTAL_REQUESTS=2000
export ECOAIMS_LOAD_RAMP_UP_S=20
export ECOAIMS_LOAD_TIMEOUT_S=5
export ECOAIMS_LOAD_P95_THRESHOLD_MS=1200
export ECOAIMS_LOAD_429_RATIO_MAX=0.20
./ecoaims_frontend_env/bin/python scripts/load_test_http.py
```

### 3) CI Load Testing (disarankan manual/nightly)

Load testing cenderung flaky jika dijalankan pada setiap PR. Rekomendasi:
- jalankan via `workflow_dispatch` (manual) atau schedule nightly
- gunakan threshold konservatif
- simpan output artefak (JSON/log)

Jika ingin dijalankan pada CI, pastikan pipeline bisa menyalakan stack backend+frontend terlebih dahulu (atau menarget staging URL yang stabil).
