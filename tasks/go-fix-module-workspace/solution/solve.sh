#!/usr/bin/env bash
set -euo pipefail

cd /app
export GOWORK=/app/go.work

cat > /app/go.mod <<'EOF'
module ledger.local/harbor

go 1.22
EOF

cat > /app/go.work <<'EOF'
go 1.22

use (
	.
)
EOF

mkdir -p /app/bin
go test ./...
go build -o /app/bin/ledger ./cmd/ledger
cmp -s <(/app/bin/ledger) <(printf '%s\n' 'ledger: ready (42)')
