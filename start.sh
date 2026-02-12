#!/bin/bash
# Compile translation files
echo "Compiling translation files..."
cd locales

# Check if we have the tools available
if ! command -v msgfmt &> /dev/null; then
    echo "Warning: msgfmt not found, installing gettext..."
    apt-get update && apt-get install -y gettext || echo "Could not install gettext"
else
    # Compile translations
    for i in *.po; do
        folder="compiled/${i%%.*}/LC_MESSAGES/"
        mkdir -p "$folder"
        msgfmt "$i" -o "$folder/all.mo"
        echo "Compiled: $i"
    done
    echo "Translation compilation complete!"
fi

cd ..

# Start the bot
echo "Starting bot..."
python PUBobot2.py
