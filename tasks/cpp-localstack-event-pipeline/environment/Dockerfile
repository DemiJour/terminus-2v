# Extend the official LocalStack image so the edge API and the task files share one container.
# The stock entrypoint starts LocalStack; Harbor's compose `command: sleep infinity` is ignored by
# docker-entrypoint.sh (it always execs localstack-supervisor), which keeps the edge up.
FROM localstack/localstack:3.8.1

USER root
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    awscli \
    cmake \
    g++ \
    jq \
    libcurl4-openssl-dev \
    make \
    pkg-config \
    python3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV AWS_ACCESS_KEY_ID=test
ENV AWS_SECRET_ACCESS_KEY=test
ENV AWS_DEFAULT_REGION=us-east-1

# Limit started services (community); matches task needs.
ENV SERVICES=s3,sns,sqs,iam

COPY project/ /app/
RUN chmod -R a+rX /app

# The upstream image uses a tight healthcheck (`localstack status services`, 15s start period).
# With SERVICES=s3,sns,sqs,iam the edge is often not ready that fast, so `docker compose up --wait`
# marks the container unhealthy and Harbor raises RuntimeError. Replace with a longer grace period
# and a simple HTTP probe against LocalStack's health route (curl is already in the base image).
HEALTHCHECK --interval=15s --timeout=15s --start-period=180s --retries=30 \
  CMD curl -fsS http://127.0.0.1:4566/_localstack/health >/dev/null || exit 1
