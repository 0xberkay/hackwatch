#!/bin/sh
# Install hackwatch onto $PATH.
#
#   ./install.sh              # -> ~/.local/bin/hackwatch
#   ./install.sh /usr/local/bin
set -eu

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
dest="${1:-${HOME}/.local/bin}"

mkdir -p "$dest"
for tool in hackwatch hack; do
    cp "$here/$tool" "$dest/$tool"
    chmod +x "$dest/$tool"
    printf 'installed %s\n' "$dest/$tool"
done
case ":${PATH}:" in
    *":$dest:"*) ;;
    *) printf 'note: %s is not on your PATH\n' "$dest" ;;
esac
