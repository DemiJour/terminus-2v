# Repair a Broken Go Module and Workspace

The small Go project at `/app` used to build cleanly, but the **module metadata** was edited incorrectly and a stray **workspace member** was added. The `.go` sources are already consistent with the intended import path `ledger.local/harbor/...`; the breakage is only in the module/workspace files.

## What you may change

- You may edit **only** `/app/go.mod` and `/app/go.work`.
- Do **not** edit any `.go` files (including tests under `/app`).

## Success criteria

The Go toolchain resolves modules relative to the directory that contains **`go.mod`**. Always **`cd /app`** before running **`go`** subcommands (the verifier also uses **`/app`** as the working directory for `go`).

From the module root `/app`:

1. **`go test ./...` completes successfully** (exit code 0).
2. **Build the command-line tool** with exactly:

   ```bash
   go build -o /app/bin/ledger ./cmd/ledger
   ```

   That command must succeed (exit code 0) and produce the binary at **`/app/bin/ledger`**.

3. **Runtime output**: running **`/app/bin/ledger`** must write **exactly one line** to standard output, with no leading or trailing whitespace on that line:

   ```text
   ledger: ready (42)
   ```

## Module path requirement

The module path declared in **`/app/go.mod`** must be exactly:

```text
ledger.local/harbor
```

This must match the import paths used by the existing Go sources (for example imports of `ledger.local/harbor/pkg/math`).

## Workspace file requirement

The file **`/app/go.work`** must list **only** the root module directory under `use` (no other workspace members). The root entry may be written as **`.`** or **`./`** (both mean the module in **`/app`**). The shipped `go.work` incorrectly references **`./deprecated-pack`**, which does not exist on disk; remove or correct that so the workspace is valid.

## Go toolchain line

The **`go`** version directive in **`/app/go.mod`** must remain **`1.22`** (the toolchain available in the environment).
