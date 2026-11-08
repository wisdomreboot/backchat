#!/bin/sh
# Rebuilds lib/codemirror.js, the editor under the margins.
# Needs Node and npm. Run from anywhere:  sh tools/codemirror/build.sh
# Steps: install the pinned packages (package-lock.json holds their integrity hashes), bundle
# entry.js, and write the bundle to lib/codemirror.js under its licence notice.
# The same packages, at the same versions, as Point First's editor.
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(cd "$here/../.." && pwd)
cd "$here"
npm ci --no-audit --no-fund --silent
npx esbuild entry.js --bundle --minify --legal-comments=none --format=iife --global-name=CM --outfile=cm.min.js
{
  printf '%s\n' "/* CodeMirror 6, the editor under Backchat's margins, with the Lezer Markdown parser."
  printf '%s\n' "   Built by tools/codemirror/build.sh from the packages pinned in tools/codemirror/package-lock.json."
  printf '%s\n' "   MIT License: CodeMirror, @lezer/markdown and their parts (c) Marijn Haverbeke and others,"
  printf '%s\n' "   https://codemirror.net. See LICENSE-codemirror.txt. */"
  cat cm.min.js
  printf '\n'
} > "$root/lib/codemirror.js"
rm -f cm.min.js
echo "lib/codemirror.js: $(wc -c < "$root/lib/codemirror.js") bytes"
