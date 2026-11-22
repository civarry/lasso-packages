#!/bin/sh
# Preview: Lasso sends {"text": the code block, "language": "html" or "svg", ...} on standard input.
# This saves the block as a page and answers with it; Lasso shows it in the code block, walled in
# (no internet except cdnjs.cloudflare.com, no other files, no popups).
set -e
input="$TMPDIR/input.json"
cat > "$input"
language=$(/usr/bin/plutil -extract language raw -o - "$input" 2>/dev/null || echo html)
case "$language" in
  svg) page="$TMPDIR/preview.svg" ;;
  *) page="$TMPDIR/index.html" ;;
esac
/usr/bin/plutil -extract text raw -o - "$input" > "$page"
if ! grep -q "[^[:space:]]" "$page"; then
  printf '{"console": "The block is empty.", "failed": true}\n'
  exit 0
fi
printf '{"console": "", "html": "%s"}\n' "$page"
