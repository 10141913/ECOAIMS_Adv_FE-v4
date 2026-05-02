#!/usr/bin/env bash
# =============================================================================
# build-push.sh — Build & Push ECOAIMS Docker Images to Docker Hub
# =============================================================================
# Usage:
#   chmod +x build-push.sh
#   ./build-push.sh              # Build + push with 'latest' tag
#   ./build-push.sh v1.0.0       # Build + push with version tag + 'latest'
#   ./build-push.sh --no-push    # Build only (no push)
#   ./build-push.sh v1.0.0 --no-push  # Build with version tag, no push
# =============================================================================
set -euo pipefail

DOCKER_HUB_USER="juliansyah"
BACKEND_DIR="/Users/juliansyah/Documents/UNDIP/Disertasi/4. Apps/pythonProject/ECO_AIMS/ECOAIMS_Adv_BE v-4"
FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"

VERSION="${1:-latest}"
NO_PUSH=false

if [ "${2:-}" = "--no-push" ] || [ "${1:-}" = "--no-push" ]; then
    NO_PUSH=true
    if [ "${1:-}" = "--no-push" ]; then
        VERSION="latest"
    fi
fi

echo "=========================================="
echo " ECOAIMS Docker Image Builder"
echo "=========================================="
echo "Docker Hub User : ${DOCKER_HUB_USER}"
echo "Version Tag     : ${VERSION}"
echo "Push to Hub     : $([ "${NO_PUSH}" = true ] && echo 'NO (build only)' || echo 'YES')"
echo "Backend Dir     : ${BACKEND_DIR}"
echo "Frontend Dir    : ${FRONTEND_DIR}"
echo "=========================================="

# ── 1. Build Backend Image ──────────────────────────────────────────────────
echo ""
echo ">>> Building backend image: ${DOCKER_HUB_USER}/ecoaims-backend:${VERSION} ..."
docker build \
    -t "${DOCKER_HUB_USER}/ecoaims-backend:${VERSION}" \
    -t "${DOCKER_HUB_USER}/ecoaims-backend:latest" \
    -f "${BACKEND_DIR}/Dockerfile" \
    "${BACKEND_DIR}"

echo ">>> Backend image built successfully."

# ── 2. Build Frontend Image ─────────────────────────────────────────────────
echo ""
echo ">>> Building frontend image: ${DOCKER_HUB_USER}/ecoaims-frontend:${VERSION} ..."
docker build \
    -t "${DOCKER_HUB_USER}/ecoaims-frontend:${VERSION}" \
    -t "${DOCKER_HUB_USER}/ecoaims-frontend:latest" \
    -f "${FRONTEND_DIR}/Dockerfile" \
    "${FRONTEND_DIR}"

echo ">>> Frontend image built successfully."

# ── 3. Push to Docker Hub (optional) ────────────────────────────────────────
if [ "${NO_PUSH}" = false ]; then
    echo ""
    echo ">>> Pushing backend image to Docker Hub ..."
    docker push "${DOCKER_HUB_USER}/ecoaims-backend:${VERSION}"
    docker push "${DOCKER_HUB_USER}/ecoaims-backend:latest"

    echo ""
    echo ">>> Pushing frontend image to Docker Hub ..."
    docker push "${DOCKER_HUB_USER}/ecoaims-frontend:${VERSION}"
    docker push "${DOCKER_HUB_USER}/ecoaims-frontend:latest"

    echo ""
    echo "=========================================="
    echo " All images built and pushed successfully!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo " Images built locally (not pushed)."
    echo " To push later, run:"
    echo "   docker push ${DOCKER_HUB_USER}/ecoaims-backend:${VERSION}"
    echo "   docker push ${DOCKER_HUB_USER}/ecoaims-frontend:${VERSION}"
    echo "=========================================="
fi

# ── 4. List images ──────────────────────────────────────────────────────────
echo ""
echo ">>> Local images:"
docker images --filter "reference=${DOCKER_HUB_USER}/ecoaims-*"
