# ECOAIMS Quickstart (Developer)

## Prasyarat

- Python tersedia dan virtualenv `ecoaims_frontend_env/` sudah ada (atau buat sendiri).
- Port default:
  - Backend FastAPI: 8008
  - Frontend Dash: 8050

## Konfigurasi Env (Kanonik)

```bash
export ECOAIMS_API_BASE_URL="http://127.0.0.1:8008"
```

Simulasi lokal untuk Monitoring/Optimization hanya jika eksplisit:

```bash
export ALLOW_LOCAL_SIMULATION_FALLBACK=true
```

Legacy fallback (opsional, hanya jika Anda memang perlu backend lama):

```bash
export API_BASE_URL="http://ip-backend-anda:8000"
```

## Daily Development Flow

```bash
make check
```

## Before Merge

```bash
make check-all
```

## Pre-commit (Ringan)

```bash
make check
```

## Menjalankan Aplikasi

```bash
bash ./run_dev.sh
```

Stop:

```bash
bash ./stop_dev.sh
```

## Smoke Browser (Opsional)

```bash
./ecoaims_frontend_env/bin/python -m pip install -r ecoaims_frontend/requirements-dev.txt
./ecoaims_frontend_env/bin/python -m playwright install chromium
make smoke-browser
```

## Contract Negotiation (Pre-flight, Opsional)

Frontend dapat melakukan pre-flight compatibility check lewat `OPTIONS` sebelum memanggil endpoint runtime tertentu.

Mode yang umum dipakai:

```bash
# Baseline (tanpa negotiation)
export ECOAIMS_CONTRACT_NEGOTIATION_ENABLED=false

# Warn (negotiation aktif, tidak memblok)
export ECOAIMS_CONTRACT_NEGOTIATION_ENABLED=true
export ECOAIMS_CONTRACT_NEGOTIATION_REQUIRED=false
export ECOAIMS_CONTRACT_MODE=lenient

# Fail-closed (negotiation wajib, blok jika unavailable/incompatible)
export ECOAIMS_CONTRACT_NEGOTIATION_ENABLED=true
export ECOAIMS_CONTRACT_NEGOTIATION_REQUIRED=true
export ECOAIMS_CONTRACT_MODE=strict
```

## Load/Stress Test FE (Dash callback loop)

Target ini me-loop request `/_dash-update-component` untuk mengukur stabilitas dan latency (p50/p95/max) pada Monitoring dan/atau Comparison.

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=5000
export ECOAIMS_SMOKE_DASH_LOOP_TARGETS=monitoring,comparison
export ECOAIMS_SMOKE_DASH_LOOP_SLEEP_MS=0
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Untuk uji lebih agresif (traffic tinggi):

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=20000
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Untuk uji skala besar (hingga 50.000 iterasi):

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=50000
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
export ECOAIMS_SMOKE_DASH_LOOP_TARGETS=monitoring,comparison
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Untuk uji ekstrem (100k–200k iterasi), gunakan sampling agar memori tetap stabil:

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=100000
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Untuk uji ekstrem lanjutan (>200k iterasi):

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=250000
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Untuk uji beban ekstrem (500k–1 juta iterasi), pertahankan sampling dan naikkan progress interval:

```bash
export ECOAIMS_SMOKE_DASH_LOOP_ITERS=500000
export ECOAIMS_SMOKE_DASH_LOOP_CONCURRENCY=6
export ECOAIMS_SMOKE_DASH_LOOP_SAMPLE_MAX=50000
export ECOAIMS_SMOKE_DASH_LOOP_PROGRESS_EVERY=10000
./ecoaims_frontend_env/bin/python scripts/smoke_runtime.py
```

Output `DASH_LOOP progress` sekarang menyertakan `cpu`, `rss_kb`, `vsz_kb` dan output akhir menyertakan `peak_cpu` dan `peak_rss_kb` untuk monitoring cepat selama uji beban.

## Simulasi kondisi jaringan (Playwright)

Contoh menjalankan smoke tabs pada berbagai profil jaringan:

```bash
ECOAIMS_NETWORK_PROFILES=wifi,4g,edge,3g,timeout ./ecoaims_frontend_env/bin/python scripts/smoke_browser_tabs_playwright.py
```

Tambahan profil yang tersedia:
- `wifi_high_latency` (Wi-Fi latency tinggi)
- `wifi_interference_high` (Wi-Fi noise/interferensi tinggi + jitter)
- `3g_high_latency` (3G + latency tinggi)
- `4g_interference` (4G/LTE dengan interferensi tinggi + jitter)
- `satellite` (latency sangat tinggi + jitter besar)
- `5g` (latency rendah)
- `roaming` (latency + jitter tinggi, sering unstable)
- `vpn` (latency tinggi + jitter)

Timeout lebih lama (misal 60 detik) untuk kondisi jaringan terburuk:

```bash
export ECOAIMS_SMOKE_TIMEOUT_MS=60000
ECOAIMS_NETWORK_PROFILES=3g_high_latency,wifi_interference_high,vpn ./ecoaims_frontend_env/bin/python scripts/smoke_browser_tabs_playwright.py
```

## Visual regression (lebih sensitif)

```bash
export ECOAIMS_VISUAL_DIFF_THRESHOLD=0.0003
./ecoaims_frontend_env/bin/python scripts/visual_regression_playwright.py
```

## Monitoring CPU/RAM (macOS)

Contoh sampling 1 detik untuk proses FE (jalankan FE dulu, lalu isi FE_PID):

```bash
export FE_PID=$(pgrep -f "ecoaims_frontend/app.py" | head -n 1)
(
  echo "ts,pid,cpu,rss_kb,vsz_kb"
  while kill -0 "$FE_PID" 2>/dev/null; do
    ts=$(date +%s)
    ps -o pid=,%cpu=,rss=,vsz= -p "$FE_PID" | awk -v ts="$ts" '{print ts "," $1 "," $2 "," $3 "," $4}'
    sleep 1
  done
) > fe_resource.csv &
```

## Troubleshooting Singkat

- Jika `make smoke` gagal karena port sudah terpakai, `run_dev.sh` akan memilih port berikutnya yang tersedia dan `make smoke` akan tetap berjalan.
- Jika backend down dan `ALLOW_LOCAL_SIMULATION_FALLBACK` tidak diaktifkan, Monitoring/Optimization akan menampilkan error UI (ini perilaku yang diinginkan).
