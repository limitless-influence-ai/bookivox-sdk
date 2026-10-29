#!/usr/bin/env bash
# Regenerate the Bookivox SDKs from the live OpenAPI schema.
#
#   ./generate_sdk.sh                # fetch from BOOKIVOX_OPENAPI_URL (default: local API)
#   ./generate_sdk.sh --spec x.json  # use a local schema file
#   ./generate_sdk.sh --check        # CI: fail if generated files are out of date
set -euo pipefail
cd "$(dirname "$0")"
exec "${PYTHON:-python3}" generate_sdk.py "$@"
