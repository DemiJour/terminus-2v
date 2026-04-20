# Pinned base (immutable digest per Ubuntu multi-arch manifest).
FROM ubuntu:24.04@sha256:c4a8d5503dfb2a3eb8ab5f807da5bc69a85730fb49b5cfca2330194ebcc41c7b

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# git for bisect; python3 for the reference solution's report.json helper (stdlib only).
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
    git \
    python3 \
  && rm -rf /var/lib/apt/lists/*

ENV GIT_AUTHOR_DATE="2024-01-15 10:00:00 +0000" \
    GIT_COMMITTER_DATE="2024-01-15 10:00:00 +0000"
RUN mkdir -p /app/repo && cd /app/repo && \
    git init && \
    git config user.email "dev@example.com" && \
    git config user.name "Dev" && \
    mkdir -p src && \
    echo "version 1" > src/main.cpp && git add src/main.cpp && git commit -m "Initial commit" && \
    GIT_AUTHOR_DATE="2024-01-15 10:01:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:01:00 +0000" \
    echo "feature A" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature A" && \
    GIT_AUTHOR_DATE="2024-01-15 10:02:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:02:00 +0000" \
    echo "feature B" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature B" && \
    GIT_AUTHOR_DATE="2024-01-15 10:03:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:03:00 +0000" \
    echo "feature C" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature C" && \
    GIT_AUTHOR_DATE="2024-01-15 10:04:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:04:00 +0000" \
    echo "feature D" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature D" && \
    GIT_AUTHOR_DATE="2024-01-15 10:05:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:05:00 +0000" \
    echo "REF: BUG_INTRODUCED" >> src/main.cpp && git add src/main.cpp && git commit -m "Add ref to bug constant" && \
    GIT_AUTHOR_DATE="2024-01-15 10:06:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:06:00 +0000" \
    echo "BUG_INTRODUCED" >> src/main.cpp && git add src/main.cpp && git commit -m "Introduce bug" && \
    GIT_AUTHOR_DATE="2024-01-15 10:07:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:07:00 +0000" \
    printf 'BUG_INTRODUCED \n' >> src/main.cpp && git add src/main.cpp && git commit -m "Add bug tag with space" && \
    GIT_AUTHOR_DATE="2024-01-15 10:08:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:08:00 +0000" \
    echo "// BUG_INTRODUCED" >> src/main.cpp && git add src/main.cpp && git commit -m "Add comment" && \
    GIT_AUTHOR_DATE="2024-01-15 10:09:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:09:00 +0000" \
    echo "feature E" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature E" && \
    GIT_AUTHOR_DATE="2024-01-15 10:10:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:10:00 +0000" \
    echo "feature F" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature F" && \
    GIT_AUTHOR_DATE="2024-01-15 10:11:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:11:00 +0000" \
    echo "feature G" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature G" && \
    GIT_AUTHOR_DATE="2024-01-15 10:12:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:12:00 +0000" \
    echo "feature H" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature H" && \
    GIT_AUTHOR_DATE="2024-01-15 10:13:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:13:00 +0000" \
    echo "feature I" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature I" && \
    GIT_AUTHOR_DATE="2024-01-15 10:14:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:14:00 +0000" \
    echo "feature J" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature J" && \
    GIT_AUTHOR_DATE="2024-01-15 10:15:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:15:00 +0000" \
    echo "feature K" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature K" && \
    GIT_AUTHOR_DATE="2024-01-15 10:16:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:16:00 +0000" \
    echo "feature L" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature L" && \
    GIT_AUTHOR_DATE="2024-01-15 10:17:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:17:00 +0000" \
    echo "feature M" >> src/main.cpp && git add src/main.cpp && git commit -m "Add feature M" && \
    GIT_AUTHOR_DATE="2024-01-15 10:18:00 +0000" GIT_COMMITTER_DATE="2024-01-15 10:18:00 +0000" \
    echo "checkpoint" >> src/main.cpp && git add src/main.cpp && git commit -m "chore: checkpoint"
