#!/usr/bin/env bash
set -euo pipefail

version="${1:?Usage: package-release.sh <version> [output-directory]}"
output_directory="${2:-dist}"
script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_directory="$(cd "${script_directory}/.." && pwd)"
staging_directory="$(mktemp -d)"

cleanup() {
  rm -rf "${staging_directory}"
}
trap cleanup EXIT

mkdir -p "${output_directory}"

prepare_bundle() {
  local platform="$1"
  local launcher="$2"
  local bundle_directory="${staging_directory}/furigana-web-${version}-${platform}/furigana-web"

  mkdir -p "${bundle_directory}/scripts"
  cp "${project_directory}/docker-compose.release.yml" "${bundle_directory}/docker-compose.yml"
  cp "${project_directory}/.env.example" "${bundle_directory}/.env.example"
  cp "${project_directory}/README.md" "${bundle_directory}/README.md"
  cp "${project_directory}/LICENSE" "${bundle_directory}/LICENSE"
  cp "${project_directory}/scripts/${launcher}" "${bundle_directory}/scripts/${launcher}"
}

prepare_bundle "windows" "start-windows.ps1"
prepare_bundle "macos" "start-macos.command"
chmod +x "${staging_directory}/furigana-web-${version}-macos/furigana-web/scripts/start-macos.command"

(
  cd "${staging_directory}/furigana-web-${version}-windows"
  python3 -m zipfile -c \
    "${project_directory}/${output_directory}/furigana-web-${version}-windows.zip" \
    furigana-web
)

tar -C "${staging_directory}/furigana-web-${version}-macos" \
  -czf "${project_directory}/${output_directory}/furigana-web-${version}-macos.tar.gz" \
  furigana-web

cp "${project_directory}/docker-compose.release.yml" \
  "${project_directory}/${output_directory}/docker-compose.release.yml"

(
  cd "${project_directory}/${output_directory}"
  sha256sum \
    "furigana-web-${version}-windows.zip" \
    "furigana-web-${version}-macos.tar.gz" \
    docker-compose.release.yml > SHA256SUMS.txt
)
