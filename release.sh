#!/bin/bash

# Define release name and version
RELEASE_NAME="aida"
VERSION="0.1" # Alpha 0.1
ARCHIVE_NAME="${RELEASE_NAME}-v${VERSION}-alpha"
BUILD_DIR="./${ARCHIVE_NAME}_build"
FINAL_ARCHIVE="./${ARCHIVE_NAME}.tar.gz"

echo "--- Preparing Aida Release v${VERSION} ---"

# 1. Create a clean build directory
echo "Creating build directory: ${BUILD_DIR}"
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# 2. Copy necessary files
echo "Copying project files..."
# Use rsync for efficient copying and exclusion
# Copy everything from current directory into BUILD_DIR
rsync -a \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.log' \
    --exclude '.claude' \
    --exclude 'release.sh' \
    ./ "${BUILD_DIR}/"

# Ensure run.sh is executable
echo "Setting executable permissions for run.sh"
chmod +x "${BUILD_DIR}/run.sh"

# 3. Create the archive
echo "Creating archive: ${FINAL_ARCHIVE}"
# -C changes directory before archiving, so the archive doesn't contain the full path
tar -czvf "${FINAL_ARCHIVE}" -C "$(dirname "${BUILD_DIR}")" "$(basename "${BUILD_DIR}")"

# 4. Clean up build directory
echo "Cleaning up build directory..."
rm -rf "${BUILD_DIR}"

echo "--- Release v${VERSION} created at ${FINAL_ARCHIVE} ---"
echo "You can now distribute ${FINAL_ARCHIVE}"
