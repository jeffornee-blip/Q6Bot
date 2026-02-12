#!/bin/bash
set -e  # Exit on error

echo "=========================================="
echo "Compiling translation files..."
echo "=========================================="
cd locales

# Check if we have the tools available
if ! command -v msgfmt &> /dev/null; then
    echo "[WARNING] msgfmt not found, installing gettext..."
    if apt-get update && apt-get install -y gettext; then
        echo "[SUCCESS] gettext installed"
    else
        echo "[WARNING] Could not install gettext, translations will be skipped"
    fi
else
    echo "[INFO] msgfmt found, compiling translations..."
    for i in *.po; do
        folder="compiled/${i%%.*}/LC_MESSAGES/"
        mkdir -p "$folder"
        msgfmt "$i" -o "$folder/all.mo"
        echo "[OK] Compiled: $i"
    done
    echo "[SUCCESS] Translation compilation complete!"
fi

cd ..

echo ""
echo "=========================================="
echo "Starting Q6Bot..."
echo "=========================================="
exec python PUBobot2.py
