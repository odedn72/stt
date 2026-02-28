#!/usr/bin/env bash
# =============================================================================
# build_app.sh — Build SystemSTT as a standalone macOS .app bundle
#
# Usage:
#   ./scripts/build_app.sh          # Build .app bundle
#   ./scripts/build_app.sh --dmg    # Build .app + create DMG installer
#   ./scripts/build_app.sh --clean  # Remove build artifacts first
#
# Prerequisites:
#   pip install pyinstaller
#   (optional) brew install create-dmg   # for --dmg flag
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

APP_NAME="SystemSTT"
APP_VERSION=$(python -c "from systemstt import __version__; print(__version__)" 2>/dev/null || echo "0.1.0")
DIST_DIR="${PROJECT_ROOT}/dist"
BUILD_DIR="${PROJECT_ROOT}/build"
APP_BUNDLE="${DIST_DIR}/${APP_NAME}.app"
DMG_NAME="${APP_NAME}-${APP_VERSION}-macos.dmg"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
CREATE_DMG=false
CLEAN_FIRST=false

for arg in "$@"; do
    case "$arg" in
        --dmg)   CREATE_DMG=true ;;
        --clean) CLEAN_FIRST=true ;;
        --help|-h)
            echo "Usage: $0 [--clean] [--dmg]"
            echo ""
            echo "  --clean   Remove build/ and dist/ before building"
            echo "  --dmg     Create a DMG installer after building the .app"
            exit 0
            ;;
        *)
            error "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
info "SystemSTT build script v${APP_VERSION}"
info "Project root: ${PROJECT_ROOT}"

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [[ "$PYTHON_MAJOR" -lt 3 ]] || [[ "$PYTHON_MAJOR" -eq 3 && "$PYTHON_MINOR" -lt 11 ]]; then
    error "Python 3.11+ is required (found: ${PYTHON_VERSION})"
    exit 1
fi
info "Python version: ${PYTHON_VERSION}"

# Check PyInstaller
if ! command -v pyinstaller &>/dev/null; then
    error "PyInstaller not found. Install it: pip install pyinstaller"
    exit 1
fi
info "PyInstaller: $(pyinstaller --version)"

# Check for spec file
if [[ ! -f "${PROJECT_ROOT}/systemstt.spec" ]]; then
    error "systemstt.spec not found in project root"
    exit 1
fi

# ---------------------------------------------------------------------------
# Clean if requested
# ---------------------------------------------------------------------------
if $CLEAN_FIRST; then
    info "Cleaning previous build artifacts..."
    rm -rf "${BUILD_DIR}" "${DIST_DIR}"
    success "Clean complete"
fi

# ---------------------------------------------------------------------------
# Run linting and tests before building (fail fast)
# ---------------------------------------------------------------------------
info "Running pre-build checks..."

cd "${PROJECT_ROOT}"

info "  Checking code with ruff..."
if ! ruff check src/ tests/ --quiet; then
    error "Lint check failed. Fix issues before building."
    exit 1
fi
success "  Lint passed"

info "  Running tests..."
if ! pytest --quiet --tb=short; then
    error "Tests failed. Fix test failures before building."
    error "Run 'make test' for full output."
    exit 1
fi
success "  Tests passed"

# ---------------------------------------------------------------------------
# Build with PyInstaller
# ---------------------------------------------------------------------------
info "Building ${APP_NAME}.app with PyInstaller..."

cd "${PROJECT_ROOT}"
pyinstaller systemstt.spec \
    --noconfirm \
    --clean \
    --log-level WARN

if [[ ! -d "${APP_BUNDLE}" ]]; then
    error "Build failed: ${APP_BUNDLE} not created"
    exit 1
fi

APP_SIZE=$(du -sh "${APP_BUNDLE}" | cut -f1)
success "Build complete: ${APP_BUNDLE} (${APP_SIZE})"

# ---------------------------------------------------------------------------
# Create DMG if requested
# ---------------------------------------------------------------------------
if $CREATE_DMG; then
    info "Creating DMG installer..."

    DMG_PATH="${DIST_DIR}/${DMG_NAME}"

    if command -v create-dmg &>/dev/null; then
        # Use create-dmg for a polished DMG with background and icon layout
        create-dmg \
            --volname "${APP_NAME}" \
            --volicon "${PROJECT_ROOT}/assets/icons/app-icon.icns" 2>/dev/null || true \
            --window-pos 200 120 \
            --window-size 600 400 \
            --icon-size 100 \
            --icon "${APP_NAME}.app" 150 185 \
            --hide-extension "${APP_NAME}.app" \
            --app-drop-link 450 185 \
            --no-internet-enable \
            "${DMG_PATH}" \
            "${APP_BUNDLE}" \
        && success "DMG created: ${DMG_PATH}" \
        || {
            warn "create-dmg failed, falling back to hdiutil..."
            hdiutil create -volname "${APP_NAME}" \
                -srcfolder "${APP_BUNDLE}" \
                -ov -format UDZO \
                "${DMG_PATH}"
            success "DMG created: ${DMG_PATH}"
        }
    else
        # Fallback: use macOS built-in hdiutil
        info "create-dmg not found, using hdiutil (install via: brew install create-dmg)"
        hdiutil create -volname "${APP_NAME}" \
            -srcfolder "${APP_BUNDLE}" \
            -ov -format UDZO \
            "${DMG_PATH}"
        success "DMG created: ${DMG_PATH}"
    fi

    DMG_SIZE=$(du -sh "${DMG_PATH}" | cut -f1)
    info "DMG size: ${DMG_SIZE}"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
info "=== Build Summary ==="
info "  App:     ${APP_BUNDLE}"
info "  Version: ${APP_VERSION}"
info "  Size:    ${APP_SIZE}"
if $CREATE_DMG; then
    info "  DMG:     ${DIST_DIR}/${DMG_NAME}"
fi
echo ""
success "Build complete!"
