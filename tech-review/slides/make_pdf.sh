#!/bin/sh
# Render slides.html to slides.pdf (one 1280x720 page per slide) with headless Chrome.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="$DIR/slides.pdf" "file://$DIR/slides.html" >/dev/null 2>&1
echo "wrote $DIR/slides.pdf"
