# Pinned base: golang official bookworm (amd64 manifest digest from hub.docker.com)
FROM golang:1.22-bookworm@sha256:cac8fb1c85bf96316112f5dd2671c8da0c19d2dfce88af9551b3141499a59eaf

RUN apt-get update \
  && apt-get install -y --no-install-recommends gcc libc6-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY app/ /app/

RUN chmod +x /app/setup.sh
