#!/bin/sh
set -eu

REPOSITORY_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RUNTIME_DIRECTORY="$REPOSITORY_ROOT/.runtime"
DOWNLOADS_DIRECTORY="$RUNTIME_DIRECTORY/downloads"
VERSIONS_FILE="$REPOSITORY_ROOT/bootstrap/runtime-versions.env"

# The metadata file contains only project-controlled KEY=value version pins.
# shellcheck disable=SC1090
. "$VERSIONS_FILE"

write_step() {
    printf '\n==> %s\n' "$1"
}

assert_runtime_path() {
    case "$1" in
        "$RUNTIME_DIRECTORY"/*) ;;
        *)
            printf 'Refusing to modify a path outside %s: %s\n' "$RUNTIME_DIRECTORY" "$1" >&2
            exit 1
            ;;
    esac
}

remove_runtime_path() {
    assert_runtime_path "$1"
    if [ -e "$1" ]; then
        rm -rf "$1"
    fi
}

reset_runtime_directory() {
    remove_runtime_path "$1"
    mkdir -p "$1"
}

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d ' ' -f 1
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | cut -d ' ' -f 1
    else
        printf 'A SHA-256 utility (sha256sum or shasum) is required.\n' >&2
        exit 1
    fi
}

get_verified_download() {
    download_uri=$1
    download_destination=$2
    download_expected_hash=$3
    assert_runtime_path "$download_destination"

    if [ -f "$download_destination" ]; then
        download_existing_hash=$(sha256_file "$download_destination")
        if [ "$download_existing_hash" = "$download_expected_hash" ]; then
            printf 'Using verified cached download: %s\n' "$(basename "$download_destination")"
            return
        fi
    fi

    download_partial="$download_destination.part"
    rm -f "$download_partial"
    printf 'Downloading %s\n' "$download_uri"
    if command -v curl >/dev/null 2>&1; then
        curl --proto '=https' --tlsv1.2 --fail --location --silent --show-error \
            "$download_uri" --output "$download_partial"
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only --quiet --output-document="$download_partial" "$download_uri"
    else
        printf 'curl or wget is required for the first installation.\n' >&2
        exit 1
    fi

    download_actual_hash=$(sha256_file "$download_partial")
    if [ "$download_actual_hash" != "$download_expected_hash" ]; then
        rm -f "$download_partial"
        printf 'Checksum mismatch for %s. Expected %s, received %s.\n' \
            "$download_uri" "$download_expected_hash" "$download_actual_hash" >&2
        exit 1
    fi
    mv -f "$download_partial" "$download_destination"
}

machine_os=$(uname -s)
machine_arch=$(uname -m)

case "$machine_arch" in
    x86_64 | amd64) architecture=X64 ;;
    arm64 | aarch64) architecture=ARM64 ;;
    *)
        printf 'Unsupported architecture: %s. Supported: x64, ARM64.\n' "$machine_arch" >&2
        exit 1
        ;;
esac

case "$machine_os-$architecture" in
    Darwin-X64)
        uv_archive_name=$UV_MACOS_X64_FILE
        uv_archive_hash=$UV_MACOS_X64_SHA256
        node_archive_name=$NODE_MACOS_X64_FILE
        node_archive_hash=$NODE_MACOS_X64_SHA256
        ;;
    Darwin-ARM64)
        uv_archive_name=$UV_MACOS_ARM64_FILE
        uv_archive_hash=$UV_MACOS_ARM64_SHA256
        node_archive_name=$NODE_MACOS_ARM64_FILE
        node_archive_hash=$NODE_MACOS_ARM64_SHA256
        ;;
    Linux-X64)
        uv_archive_name=$UV_LINUX_X64_FILE
        uv_archive_hash=$UV_LINUX_X64_SHA256
        node_archive_name=$NODE_LINUX_X64_FILE
        node_archive_hash=$NODE_LINUX_X64_SHA256
        ;;
    Linux-ARM64)
        uv_archive_name=$UV_LINUX_ARM64_FILE
        uv_archive_hash=$UV_LINUX_ARM64_SHA256
        node_archive_name=$NODE_LINUX_ARM64_FILE
        node_archive_hash=$NODE_LINUX_ARM64_SHA256
        ;;
    *)
        printf 'Unsupported operating system and architecture: %s %s.\n' \
            "$machine_os" "$machine_arch" >&2
        exit 1
        ;;
esac

mkdir -p "$DOWNLOADS_DIRECTORY"

uv_directory="$RUNTIME_DIRECTORY/uv"
uv_executable="$uv_directory/uv"
uv_installed_version=
if [ -x "$uv_executable" ]; then
    uv_installed_version=$("$uv_executable" --version 2>/dev/null || true)
fi

case "$uv_installed_version" in
    "uv $UV_VERSION "*) printf 'Using local uv %s\n' "$UV_VERSION" ;;
    *)
        write_step "Installing uv $UV_VERSION locally"
        uv_archive="$DOWNLOADS_DIRECTORY/$uv_archive_name"
        uv_uri="https://releases.astral.sh/github/uv/releases/download/$UV_VERSION/$uv_archive_name"
        get_verified_download "$uv_uri" "$uv_archive" "$uv_archive_hash"

        uv_staging="$RUNTIME_DIRECTORY/staging-uv"
        reset_runtime_directory "$uv_staging"
        tar -xzf "$uv_archive" -C "$uv_staging"
        uv_candidate=$(find "$uv_staging" -type f -name uv | head -n 1)
        if [ -z "$uv_candidate" ]; then
            printf 'The verified uv archive did not contain uv.\n' >&2
            exit 1
        fi

        reset_runtime_directory "$uv_directory"
        cp "$uv_candidate" "$uv_executable"
        chmod +x "$uv_executable"
        remove_runtime_path "$uv_staging"
        ;;
esac

export UV_CACHE_DIR="$RUNTIME_DIRECTORY/uv-cache"
export UV_PYTHON_BIN_DIR="$RUNTIME_DIRECTORY/python-bin"
export UV_PYTHON_INSTALL_DIR="$RUNTIME_DIRECTORY/python"
export UV_NO_MODIFY_PATH=1

write_step "Installing managed Python $PYTHON_VERSION locally"
"$uv_executable" python install "$PYTHON_VERSION" --install-dir "$UV_PYTHON_INSTALL_DIR" --no-bin

write_step "Synchronizing locked Python dependencies"
(
    cd "$REPOSITORY_ROOT"
    "$uv_executable" sync --locked --all-groups --managed-python --python "$PYTHON_VERSION"
)

node_directory="$RUNTIME_DIRECTORY/node"
node_executable="$node_directory/bin/node"
node_installed_version=
if [ -x "$node_executable" ]; then
    node_installed_version=$("$node_executable" --version 2>/dev/null || true)
fi

if [ "$node_installed_version" != "v$NODE_VERSION" ]; then
    write_step "Installing Node.js $NODE_VERSION locally"
    node_archive="$DOWNLOADS_DIRECTORY/$node_archive_name"
    node_uri="https://nodejs.org/dist/v$NODE_VERSION/$node_archive_name"
    get_verified_download "$node_uri" "$node_archive" "$node_archive_hash"

    node_staging="$RUNTIME_DIRECTORY/staging-node"
    reset_runtime_directory "$node_staging"
    tar -xzf "$node_archive" -C "$node_staging"
    node_candidate=$(find "$node_staging" -type f -path '*/bin/node' | head -n 1)
    if [ -z "$node_candidate" ]; then
        printf 'The verified Node.js archive did not contain bin/node.\n' >&2
        exit 1
    fi

    extracted_node_directory=$(dirname "$(dirname "$node_candidate")")
    remove_runtime_path "$node_directory"
    mv "$extracted_node_directory" "$node_directory"
    remove_runtime_path "$node_staging"
else
    printf 'Using local Node.js %s\n' "$NODE_VERSION"
fi

npm_cli="$node_directory/lib/node_modules/npm/bin/npm-cli.js"
pnpm_directory="$RUNTIME_DIRECTORY/pnpm"
pnpm_cli="$pnpm_directory/lib/node_modules/pnpm/bin/pnpm.cjs"
pnpm_installed_version=
if [ -f "$pnpm_cli" ]; then
    pnpm_installed_version=$("$node_executable" "$pnpm_cli" --version 2>/dev/null || true)
fi

export npm_config_cache="$RUNTIME_DIRECTORY/npm-cache"
export npm_config_update_notifier=false
export PNPM_HOME="$pnpm_directory/bin"
export PATH="$node_directory/bin:$PNPM_HOME:$PATH"

if [ "$pnpm_installed_version" != "$PNPM_VERSION" ]; then
    write_step "Installing pnpm $PNPM_VERSION locally"
    reset_runtime_directory "$pnpm_directory"
    "$node_executable" "$npm_cli" install --global --prefix "$pnpm_directory" \
        "pnpm@$PNPM_VERSION" --no-audit --no-fund
else
    printf 'Using local pnpm %s\n' "$PNPM_VERSION"
fi

if [ ! -f "$pnpm_cli" ]; then
    printf 'pnpm was installed but its command could not be found at %s.\n' "$pnpm_cli" >&2
    exit 1
fi

write_step "Installing locked frontend dependencies"
(
    cd "$REPOSITORY_ROOT/frontend"
    "$node_executable" "$pnpm_cli" install --frozen-lockfile \
        --store-dir "$RUNTIME_DIRECTORY/pnpm-store"

    write_step "Building the frontend"
    "$node_executable" "$pnpm_cli" build
)

printf "\nJerome's Laboratory is installed.\n"
printf 'Run ./start.sh to launch it.\n'
