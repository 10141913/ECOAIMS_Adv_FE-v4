## OWASP ZAP (Baseline / Full Scan)

Dokumen ini menjelaskan cara menjalankan OWASP ZAP secara rutin untuk mendeteksi temuan umum seperti:
- XSS
- SQLi (indikasi)
- misconfiguration (CORS, headers, cookie flags)

Catatan:
- Untuk aplikasi yang butuh auth, baseline scan tanpa login biasanya hanya mencakup endpoint publik. Untuk scan yang butuh auth, gunakan ZAP Context + Auth (di luar scope dokumen ringkas ini).

### Prasyarat

- Target URL (Frontend atau Backend) dapat diakses dari runner.
- Docker terpasang (rekomendasi) atau ZAP desktop.

### 1) Baseline Scan (aman untuk rutin)

Scan ini tidak agresif (passive scan + spider ringan).

```bash
export TARGET_URL=http://127.0.0.1:8050

docker run --rm -t \
  -u zap \
  -v "$(pwd)/output/zap:/zap/wrk" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t "$TARGET_URL" \
  -r zap_baseline_report.html \
  -J zap_baseline_report.json
```

Output:
- `output/zap/zap_baseline_report.html`
- `output/zap/zap_baseline_report.json`

### 2) Full Scan (lebih agresif, jalankan di staging)

```bash
export TARGET_URL=http://127.0.0.1:8050

docker run --rm -t \
  -u zap \
  -v "$(pwd)/output/zap:/zap/wrk" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-full-scan.py -t "$TARGET_URL" \
  -r zap_full_report.html \
  -J zap_full_report.json
```

### 3) Fokus Endpoint Backend

Jika ingin fokus ke backend:

```bash
export TARGET_URL=http://127.0.0.1:8008
docker run --rm -t -u zap -v "$(pwd)/output/zap:/zap/wrk" ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t "$TARGET_URL/health" -r zap_backend_health.html -J zap_backend_health.json
```

### 4) Operational Notes

- Jalankan baseline scan nightly atau sebelum release.
- Jika ada false positive, gunakan suppression file ZAP (context/rules) dan dokumentasikan alasannya.
- Jangan memasukkan token rahasia ke command line di CI logs.
