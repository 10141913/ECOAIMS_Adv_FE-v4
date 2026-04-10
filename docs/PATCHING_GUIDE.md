## Patch Failures: Root Cause dan Mitigasi

### Root Cause umum patch failure

- Context mismatch: patch berbasis konteks baris. Jika file berubah (reformat, lint, perubahan kecil) setelah patch dibuat, patch bisa gagal walaupun perubahan semantik masih relevan.
- Patch tool hanya mencoba apply sekali: jika ada perubahan cepat/parallel edit, patch dapat gagal dan error yang terlihat minim.
- Patch menarget file path yang berbeda (rename/move) sehingga context tidak ketemu.

### Praktik yang mengurangi failure rate

- Pastikan patch dibuat dari baseline terbaru (pull, sync).
- Hindari membuat patch dari potongan file yang sudah berubah oleh formatter/linter.
- Untuk perubahan besar, pecah patch per-file/per-hunk.

### Tooling retry + validation

Repo menyediakan runner:

```bash
./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py --patch /path/to/change.diff
```

Fitur:
- retry dengan exponential backoff
- `git apply --3way` untuk toleransi konteks yang lebih baik
- report hash per file sebelum/sesudah apply, tersimpan di `output/patch_validation/`
- deteksi cepat patch sudah pernah diterapkan (`reverse_applicable=true`)
- opsi `--strip` untuk patch dengan path yang berbeda

Dry-run:

```bash
./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py --patch /path/to/change.diff --dry-run
```

Contoh jika patch punya path yang tidak standar:

```bash
./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py --patch /path/to/change.diff --strip 0
```
