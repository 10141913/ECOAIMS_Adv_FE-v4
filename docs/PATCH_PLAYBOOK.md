## Patch Playbook (Otomatis dari report)

Tujuan:
- Menurunkan risiko patch failure akibat context mismatch dengan rekomendasi parameter yang konsisten.
- Menggunakan data nyata dari report `output/patch_validation/*.json`.

### 1) Kumpulkan 3 report terakhir (failed)

Tool akan otomatis mengambil report terbaru dari folder:

```bash
./ecoaims_frontend_env/bin/python scripts/patch_playbook.py --only-failed --n 3
```

Jika output mengatakan tidak ada report, berarti belum ada patch yang dijalankan menggunakan `apply_patch_with_retry.py`.

### 2) Generate report untuk patch yang gagal

Saat patch gagal, jalankan:

```bash
./ecoaims_frontend_env/bin/python scripts/apply_patch_with_retry.py --patch /path/to/change.diff
```

Lalu ulangi playbook:

```bash
./ecoaims_frontend_env/bin/python scripts/patch_playbook.py --only-failed --n 3
```

### 3) Interpretasi rekomendasi

Rule utama yang dipakai:
- `reverse_applicable=true` → patch kemungkinan sudah diterapkan (gunakan `--dry-run` untuk memastikan).
- `failure_class=context_mismatch` → coba `--whitespace fix`, variasi `--strip`, lalu fallback `--allow-rejects`.
- `failure_class=corrupt_patch` → patch rusak, regenerate dari baseline terbaru.

Output `scripts/patch_playbook.py` menyertakan command yang bisa langsung dicopy-paste.
