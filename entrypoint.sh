#!/bin/bash
set -e

# Ensure the ledger and db directories have the correct ownership
chown -R appuser:appuser /app/ledger /app/db

# Execute the command as the non-root user
exec gosu appuser "$@"
