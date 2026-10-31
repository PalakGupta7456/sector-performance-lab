#!/usr/bin/env bash
# Rebuild every output from the raw price files in data/raw/.
# Add --fetch to download fresh prices first.
set -euo pipefail
cd "$(dirname "$0")"
if [[ "${1:-}" == "--fetch" ]]; then python src/fetch_data.py --refresh; fi
python src/build_prices.py
python src/analysis.py
python src/export_dashboard.py
python src/build_site.py PalakGupta7456 sector-performance-lab
echo "Done. Preview: python -m http.server -d docs 8000"
