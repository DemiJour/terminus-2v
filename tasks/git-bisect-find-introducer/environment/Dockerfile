# Pinned toolchain image (amd64 digest from hub.docker.com); matches other Go tasks in this repo.
FROM golang:1.22-bookworm@sha256:cac8fb1c85bf96316112f5dd2671c8da0c19d2dfce88af9551b3141499a59eaf

WORKDIR /app

# git + python3 (oracle writes report.json via stdlib; jq is not guaranteed on all runtimes).
# curl + ca-certificates so the verifier can install uv without a slow apt phase.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    git \
    python3 \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Longer history (18 commits); introducing commit in the middle. Red herrings: REF: and trailing space.
# Commit 6 = "REF: BUG_INTRODUCED", commit 7 = exact "BUG_INTRODUCED" (target), commit 8 = "BUG_INTRODUCED " (space).
# Trailing no-op commit bumps this RUN's cache key so builders do not reuse an old layer that still used src/main.py.
ENV GIT_AUTHOR_DATE="2024-01-15 10:00:00 +0000" \
    GIT_COMMITTER_DATE="2024-01-15 10:00:00 +0000"
RUN mkdir -p /app/repo && cd /app/repo && \
    git init && \
    git config user.email "dev@example.com" && \
    git config user.name "Dev" && \
    mkdir -p src && \
    echo "version 1" > src/main.go && git add src/main.go && git commit -m "Initial commit" && \
    GIT_AUTHOR_DATE="2024-01-15 10:01:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:01:00 +0000" \
    echo "feature A" >> src/main.go && git add src/main.go && git commit -m "Add feature A" && \
    GIT_AUTHOR_DATE="2024-01-15 10:02:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:02:00 +0000" \
    echo "feature B" >> src/main.go && git add src/main.go && git commit -m "Add feature B" && \
    GIT_AUTHOR_DATE="2024-01-15 10:03:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:03:00 +0000" \
    echo "feature C" >> src/main.go && git add src/main.go && git commit -m "Add feature C" && \
    GIT_AUTHOR_DATE="2024-01-15 10:04:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:04:00 +0000" \
    echo "feature D" >> src/main.go && git add src/main.go && git commit -m "Add feature D" && \
    GIT_AUTHOR_DATE="2024-01-15 10:05:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:05:00 +0000" \
    echo "REF: BUG_INTRODUCED" >> src/main.go && git add src/main.go && git commit -m "Add ref to bug constant" && \
    GIT_AUTHOR_DATE="2024-01-15 10:06:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:06:00 +0000" \
    echo "BUG_INTRODUCED" >> src/main.go && git add src/main.go && git commit -m "Introduce bug" && \
    GIT_AUTHOR_DATE="2024-01-15 10:07:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:07:00 +0000" \
    printf 'BUG_INTRODUCED \n' >> src/main.go && git add src/main.go && git commit -m "Add bug tag with space" && \
    GIT_AUTHOR_DATE="2024-01-15 10:08:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:08:00 +0000" \
    echo "// BUG_INTRODUCED" >> src/main.go && git add src/main.go && git commit -m "Add comment" && \
    GIT_AUTHOR_DATE="2024-01-15 10:09:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:09:00 +0000" \
    echo "feature E" >> src/main.go && git add src/main.go && git commit -m "Add feature E" && \
    GIT_AUTHOR_DATE="2024-01-15 10:10:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:10:00 +0000" \
    echo "feature F" >> src/main.go && git add src/main.go && git commit -m "Add feature F" && \
    GIT_AUTHOR_DATE="2024-01-15 10:11:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:11:00 +0000" \
    echo "feature G" >> src/main.go && git add src/main.go && git commit -m "Add feature G" && \
    GIT_AUTHOR_DATE="2024-01-15 10:12:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:12:00 +0000" \
    echo "feature H" >> src/main.go && git add src/main.go && git commit -m "Add feature H" && \
    GIT_AUTHOR_DATE="2024-01-15 10:13:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:13:00 +0000" \
    echo "feature I" >> src/main.go && git add src/main.go && git commit -m "Add feature I" && \
    GIT_AUTHOR_DATE="2024-01-15 10:14:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:14:00 +0000" \
    echo "feature J" >> src/main.go && git add src/main.go && git commit -m "Add feature J" && \
    GIT_AUTHOR_DATE="2024-01-15 10:15:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:15:00 +0000" \
    echo "feature K" >> src/main.go && git add src/main.go && git commit -m "Add feature K" && \
    GIT_AUTHOR_DATE="2024-01-15 10:16:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:16:00 +0000" \
    echo "feature L" >> src/main.go && git add src/main.go && git commit -m "Add feature L" && \
    GIT_AUTHOR_DATE="2024-01-15 10:17:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:17:00 +0000" \
    echo "feature M" >> src/main.go && git add src/main.go && git commit -m "Add feature M" && \
    GIT_AUTHOR_DATE="2024-01-15 10:18:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:18:00 +0000" \
    echo "TASK_IMAGE_LAYER_REV=7" >> src/main.go && git add src/main.go && git commit -m "chore: task image layer revision"
