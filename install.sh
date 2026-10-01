#!/bin/sh
# Install hackwatch onto $PATH.
#
#   ./install.sh              # -> ~/.local/bin/hackwatch
#   ./install.sh /usr/local/bin
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dest="${1:-${HOME}/.local/bin}"

mkdir -p "$dest"
cp "$here/hackwatch" "$dest/hackwatch"
chmod +x "$dest/hackwatch"

printf 'installed %s\n' "$dest/hackwatch"
case ":${PATH}:" in
    *":$dest:"*) ;;
    *) printf 'note: %s is not on your PATH\n' "$dest" ;;
esac
