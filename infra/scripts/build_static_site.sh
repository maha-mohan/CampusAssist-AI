#!/usr/bin/env bash
# Builds the widget, the admin dashboard and the demo page into ./site, ready to upload to any
# free static host (Netlify, Cloudflare Pages, Vercel, GitHub Pages).
#
#   bash infra/scripts/build_static_site.sh https://your-api.onrender.com/api
#
# Result:  site/index.html (redirects to /demo/), site/demo/, site/widget/helpdesk-widget.js, site/admin/
set -euo pipefail

API_URL="${1:?Usage: build_static_site.sh <public API URL ending in /api>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/site"

rm -rf "$OUT" && mkdir -p "$OUT/widget" "$OUT/demo"

echo "Building widget..."
(cd "$ROOT/frontend/widget" && npm install --no-audit --no-fund && npm run build)
cp "$ROOT/frontend/widget/dist/helpdesk-widget.js" "$OUT/widget/"

echo "Building admin dashboard..."
(cd "$ROOT/frontend/admin" && npm install --no-audit --no-fund && VITE_API_URL="$API_URL" npm run build)
cp -r "$ROOT/frontend/admin/dist" "$OUT/admin"

# Demo page: point the embed at the hosted API.
sed "s#data-api=\"/api\"#data-api=\"$API_URL\"#" "$ROOT/demo/index.html" > "$OUT/demo/index.html"

echo '<meta http-equiv="refresh" content="0; url=/demo/">' > "$OUT/index.html"
# Single-page-app fallback for the admin dashboard (Netlify / Cloudflare Pages format).
echo "/admin/*  /admin/index.html  200" > "$OUT/_redirects"

echo "Done. Upload the 'site' folder to your static host."
