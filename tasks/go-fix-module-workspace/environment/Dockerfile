# Pinned toolchain image (digest from Docker Hub); matches other Go tasks in this repo.
FROM golang:1.22-bookworm@sha256:cac8fb1c85bf96316112f5dd2671c8da0c19d2dfce88af9551b3141499a59eaf

WORKDIR /app

RUN mkdir -p cmd/ledger pkg/math

RUN cat > /app/go.mod <<'EOF_GOMOD'
module github.com/acme/wrongledger

go 1.22
EOF_GOMOD

RUN cat > /app/go.work <<'EOF_GOWORK'
go 1.22

use (
	.
	./deprecated-pack
)
EOF_GOWORK

RUN cat > /app/pkg/math/math.go <<'EOF_MATH'
package math

// Sum returns a + b.
func Sum(a, b int) int {
	return a + b
}
EOF_MATH

RUN cat > /app/pkg/math/math_test.go <<'EOF_MATH_TEST'
package math

import "testing"

func TestSum(t *testing.T) {
	if got := Sum(2, 3); got != 5 {
		t.Fatalf("Sum(2,3) = %d, want 5", got)
	}
}
EOF_MATH_TEST

RUN cat > /app/cmd/ledger/main.go <<'EOF_MAIN'
package main

import (
	"fmt"

	"ledger.local/harbor/pkg/math"
)

func main() {
	fmt.Printf("ledger: ready (%d)\n", math.Sum(20, 22))
}
EOF_MAIN
