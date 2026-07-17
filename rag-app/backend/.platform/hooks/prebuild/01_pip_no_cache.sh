#!/bin/bash
set -euo pipefail

cat > /etc/pip.conf <<'EOF'
[global]
no-cache-dir = true
progress-bar = off
EOF
