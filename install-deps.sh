#!/bin/bash

# Install pip dependencies for all services
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing dependencies for all services..."
echo ""

find "$REPO_ROOT/services" -name "requirements.txt" | sort | while read req; do
  service_dir="$(dirname "$req")"
  service_name="$(basename "$service_dir")"
  echo "▶ $service_name"
  pip3 install -r "$req"
  echo ""
done

echo "Done."
