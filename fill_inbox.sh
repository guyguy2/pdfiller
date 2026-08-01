#!/usr/bin/env bash
# Fill every PDF dropped in an inbox directory, asking at the terminal for
# any field with no stored default, an ambiguous (multi-value) default, or
# a signature. See fill_inbox.py for the per-field logic.
#
# Usage: ./fill_inbox.sh [inbox_dir]
#   inbox_dir defaults to <project_dir>/inbox
#
# Only fillable (AcroForm) PDFs are handled; non-fillable (scanned) PDFs
# are skipped - use the interactive /fill-pdf workflow for those.

set -euo pipefail

PDFILLER_DIR="/Users/guy/dev/automation/python/pdfiller"
INBOX="${1:-$PDFILLER_DIR/inbox}"

if [ ! -d "$INBOX" ]; then
    echo "Error: inbox directory not found: $INBOX" >&2
    exit 1
fi

uv run --project "$PDFILLER_DIR" python "$PDFILLER_DIR/fill_inbox.py" "$INBOX"
