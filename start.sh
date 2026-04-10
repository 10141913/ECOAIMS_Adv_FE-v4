#!/bin/bash

# Dapatkan direktori skrip saat ini
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Aktifkan virtual environment (sesuaikan path jika berbeda)
echo "Mengaktifkan virtual environment..."
source "$SCRIPT_DIR/ecoaims_frontend_env/bin/activate"

# Masuk ke direktori frontend
cd "$SCRIPT_DIR/ecoaims_frontend"

# Jalankan aplikasi
echo "Menjalankan aplikasi Dash..."
python app.py
