#!/bin/sh
# Installer for claude-code-env-editor.
#
#   curl -LsSf https://raw.githubusercontent.com/kraigochieng/claude-code-env-editor/main/install.sh | sh
#   curl -LsSf <same url> | sh -s -- --version 0.2.0
#
# Read this script before you run it.
set -eu

REPO="kraigochieng/claude-code-env-editor"
NAME="claude-code-env-editor"
API="https://api.github.com/repos/$REPO"
DL="https://github.com/$REPO/releases/download"

version="${CCEE_VERSION:-}"
action="install"

usage() {
  cat <<USAGE
Install $NAME.

Usage: install.sh [--version X.Y.Z] [--list] [--uninstall] [--help]

  --version X.Y.Z  Install this version. Default: the latest release.
  --list           Print the available versions and exit.
  --uninstall      Remove $NAME.
  --help           Print this text.

The environment variable CCEE_VERSION works like --version.
USAGE
}

die() { printf 'error: %s\n' "$*" >&2; exit 1; }
say() { printf '%s\n' "$*"; }

while [ $# -gt 0 ]; do
  case "$1" in
    --version) [ $# -ge 2 ] || die "--version needs a value."; version="$2"; shift 2 ;;
    --version=*) version="${1#--version=}"; shift ;;
    --list) action="list"; shift ;;
    --uninstall) action="uninstall"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
done

command -v curl >/dev/null 2>&1 || die "curl is required."

fetch() { curl -fsSL "$1"; }

list_versions() {
  fetch "$API/releases?per_page=100" 2>/dev/null \
    | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' \
    || true
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else die "sha256sum or shasum is required."; fi
}

if [ "$action" = "list" ]; then
  versions="$(list_versions)"
  [ -n "$versions" ] || die "no releases found."
  printf '%s\n' "$versions"
  exit 0
fi

if [ "$action" = "uninstall" ]; then
  command -v uv >/dev/null 2>&1 || die "uv is not installed. Nothing to remove."
  uv tool uninstall "$NAME"
  exit 0
fi

versions="$(list_versions)"
if [ -z "$version" ]; then
  version="$(fetch "$API/releases/latest" 2>/dev/null | sed -n 's/.*"tag_name": *"v\{0,1\}\([^"]*\)".*/\1/p' | head -n 1 || true)"
  [ -n "$version" ] || die "cannot find the latest release. Is there a release yet?"
fi
version="${version#v}"

if ! printf '%s\n' "$versions" | grep -qx "$version"; then
  printf 'error: version %s does not exist.\n' "$version" >&2
  [ -n "$versions" ] && { say "Available versions:" >&2; printf '%s\n' "$versions" >&2; }
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  say "uv is not installed. Installing uv from https://astral.sh/uv ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv install failed."
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT INT TERM
wheel="claude_code_env_editor-${version}-py3-none-any.whl"

say "Downloading $NAME $version ..."
curl -fsSL -o "$tmp/$wheel" "$DL/v$version/$wheel" || die "cannot download $wheel."
curl -fsSL -o "$tmp/SHA256SUMS" "$DL/v$version/SHA256SUMS" || die "cannot download SHA256SUMS."

expected="$(grep " $wheel\$" "$tmp/SHA256SUMS" | cut -d' ' -f1 || true)"
[ -n "$expected" ] || die "SHA256SUMS has no entry for $wheel."
actual="$(sha256_of "$tmp/$wheel")"
[ "$expected" = "$actual" ] || die "checksum mismatch for $wheel. The file is not installed."

uv tool install --force "$tmp/$wheel"

say "Installed $NAME $version."
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) say "Warning: $HOME/.local/bin is not in your PATH. Run: uv tool update-shell" ;;
esac
say "Run: $NAME --help"
