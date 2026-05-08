#!/bin/bash
set -e

TARGET_DIR="/app/ledger"
MOUNT_UID=$(stat -c '%u' "$TARGET_DIR")
MOUNT_GID=$(stat -c '%g' "$TARGET_DIR")

if [ "$MOUNT_UID" = "0" ]; then
    exec "$@"
else
    if ! getent group "$MOUNT_GID" > /dev/null 2>&1; then
        groupadd -g "$MOUNT_GID" appgroup
    fi
    if ! id -u "$MOUNT_UID" > /dev/null 2>&1; then
        useradd -r -u "$MOUNT_UID" -g "$MOUNT_GID" -m appuser
    fi

    exec setpriv --reuid="$MOUNT_UID" --regid="$MOUNT_GID" --init-groups "$@"
fi
