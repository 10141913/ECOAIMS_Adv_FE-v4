# Release Checklist (FE)

Checklist ini fokus pada verifikasi & hardening agar perilaku FE konsisten saat kondisi normal maupun error, serta meminimalkan regresi.

## A. Baseline (selalu)
- Jalankan pipeline standar:
  - `make release-check`
- Pastikan FE tidak menampilkan error traceback pada runtime (lihat terminal FE atau `.run/*.log` bila pakai stack-canonical).

## B. Canonical Lane (8008, fail-closed)
- Jalankan stack kanonik end-to-end:
  - `NO_OPEN=1 make stack-canonical`
- Verifikasi indikator integrasi:
  - Buka `http://127.0.0.1:8050/__runtime` (base_url=8008)
  - Buka UI dan pastikan banner menunjukkan “Canonical integration verified”
- Jalankan smoke browser (opsional, tetapi direkomendasikan sebelum demo/rilis):
  - `make smoke-browser`

## C. External Backend Lane (mis. 8009, kompatibilitas)
Tujuan lane ini: FE berjalan stabil dengan backend eksternal, tanpa crash, dan fallback/gating jelas.

- Jalankan FE mengarah ke backend eksternal:

```bash
ECOAIMS_API_BASE_URL_CANONICAL=http://127.0.0.1:8009 \
ECOAIMS_REQUIRE_CANONICAL_POLICY=false \
ECOAIMS_ALLOW_MINIMAL_STARTUP_INFO=true \
make run-frontend-canonical
```

- Jalankan diagnostik terhadap backend eksternal:
  - `BACKEND=http://127.0.0.1:8009 make doctor-stack`
- Verifikasi tab:
  - Monitoring/Optimization/Precooling/Reports tidak crash dan menampilkan pesan “not supported / placeholder” bila endpoint memang tidak tersedia.

## D. Cross-Repo Evidence (audit)
Jika Anda punya repo backend terpisah, jalankan canonical chain (tanpa browser):

```bash
ECOAIMS_BE_REPO_PATH="/path/ke/ECOAIMS_Adv_BE v-4" \
ECOAIMS_API_BASE_URL="http://127.0.0.1:8008" \
make release-check-canonical-crossrepo
```

Output artifact berada di `output/verification/`.

## E. Troubleshooting cepat
- Bersihkan log runtime lokal:
  - `make clean-run`
- Cek endpoint/kontrak spesifik:
  - `ENDPOINT_KEY="GET /api/reports/precooling-impact" make mismatch-check`
