#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

# FinderやDock経由でもHomebrewのffmpeg / ffprobeを検出できるようにする。
for yss_bin_dir in "$PWD/tools/bin" "$HOME/.homebrew/bin" /opt/homebrew/bin /usr/local/bin; do
  if [ -d "$yss_bin_dir" ]; then
    PATH="$yss_bin_dir:$PATH"
  fi
done
export PATH

if [ -x ".venv/bin/python" ]; then
  .venv/bin/python run.py
else
  python3 run.py
fi
