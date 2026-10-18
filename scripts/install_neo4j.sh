#!/usr/bin/env bash
# SUMMARY: Downloads the free Neo4j database server into this project and sets it
# up so that its database files live in the project's data/neo4j folder.
#
# - The program goes into tools/neo4j (kept out of git: anyone can re-download it).
# - The database and its log files go into data/neo4j (also kept out of git).
# - The download is checked against Neo4j's published fingerprint (a SHA-256
#   checksum), so we know the file is genuine and not corrupted.
#
# Normally run through the Makefile:  make neo4j-install

# Stop at the first error, treat unset variables as errors, and fail if any step of a pipe fails.
set -euo pipefail

# The exact Neo4j version we use, pinned so everyone gets the same one.
NEO4J_VERSION="2026.09.0"
# Neo4j's published fingerprint for that exact download file.
NEO4J_SHA256="cdaa0905d9a533bbbc474d239c268f69978982eb5ca3177666c04c9792d1c399"
# The web address of the free "Community" edition download for Mac/Linux.
NEO4J_URL="https://dist.neo4j.org/neo4j-community-${NEO4J_VERSION}-unix.tar.gz"

# The project's top folder: this script's folder ("scripts"), then one level up.
# "pwd -P" gives the real location, even when the project is opened through a shortcut (symbolic link).
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
# Where the downloaded program will be unpacked.
NEO4J_HOME="${PROJECT_ROOT}/tools/neo4j"
# Where the downloaded archive file is kept while we check and unpack it.
ARCHIVE="${PROJECT_ROOT}/tools/neo4j-${NEO4J_VERSION}.tar.gz"

# If Neo4j is already unpacked, there is nothing to do.
if [[ -x "${NEO4J_HOME}/bin/neo4j" ]]; then
  # Tell the user, then stop without changing anything.
  echo "Neo4j already installed in tools/neo4j"; exit 0
fi

# Make sure the tools folder exists.
mkdir -p "${PROJECT_ROOT}/tools"
# Download the archive only if we don't already have it (saves re-downloading ~260 MB).
if [[ ! -f "${ARCHIVE}" ]]; then
  # Fetch the file quietly, failing on any web error, following redirects.
  curl -sSfL -o "${ARCHIVE}" "${NEO4J_URL}"
fi

# Work out the fingerprint of the file we actually downloaded.
ACTUAL_SHA256="$(shasum -a 256 "${ARCHIVE}" | cut -d' ' -f1)"
# Compare it with Neo4j's published fingerprint.
if [[ "${ACTUAL_SHA256}" != "${NEO4J_SHA256}" ]]; then
  # They differ: the file is damaged or not genuine. Say so and stop.
  echo "Checksum mismatch for ${ARCHIVE}: refusing to install" >&2; exit 1
fi

# Create the folder the program will be unpacked into.
mkdir -p "${NEO4J_HOME}"
# Unpack the archive, dropping its top-level folder so files land directly in tools/neo4j.
tar -xzf "${ARCHIVE}" -C "${NEO4J_HOME}" --strip-components=1
# Delete the archive now that it's unpacked; it's no longer needed.
rm "${ARCHIVE}"

# Add our own settings to the end of Neo4j's settings file. Neo4j only accepts
# full paths with no ".." in them, so we write this project's full path in.
cat >> "${NEO4J_HOME}/conf/neo4j.conf" <<EOF

# --- Seisa project settings (added by scripts/install_neo4j.sh) ---
# Keep the database files in the project's data/neo4j folder.
server.directories.data=${PROJECT_ROOT}/data/neo4j/data
# Keep Neo4j's log files next to the database, also in the project.
server.directories.logs=${PROJECT_ROOT}/data/neo4j/logs
# Only accept connections from this computer, never from the network.
server.default_listen_address=127.0.0.1
EOF

# Make sure the database and log folders exist before the first start.
mkdir -p "${PROJECT_ROOT}/data/neo4j/data" "${PROJECT_ROOT}/data/neo4j/logs"
# Report success.
echo "Installed Neo4j ${NEO4J_VERSION} into tools/neo4j (database in data/neo4j)"
