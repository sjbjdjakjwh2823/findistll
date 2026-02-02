#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bin_dir="$repo_root/bin"
mkdir -p "$bin_dir"

arch="$(uname -m)"
case "$arch" in
  arm64) url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-arm64" ;;
  x86_64) url="https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-amd64" ;;
  *) echo "Unsupported architecture: $arch"; exit 1 ;;
esac

dest="$bin_dir/cloudflared"
curl -L "$url" -o "$dest"
chmod +x "$dest"

echo "Installed cloudflared to $dest"
