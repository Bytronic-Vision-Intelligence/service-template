# Runs .github/workflows/ locally via nektos/act.
#
# act drives the HOST docker daemon through the mounted socket, so the job
# containers are siblings of this one, not children.
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        tar \
    && rm -rf /var/lib/apt/lists/*

# docker CLI only — no daemon here, the socket is mounted in
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker

RUN curl -fsSL https://raw.githubusercontent.com/nektos/act/master/install.sh \
      | bash -s -- -b /usr/local/bin \
    && act --version

COPY entrypoint.sh /usr/local/bin/entrypoint
RUN chmod +x /usr/local/bin/entrypoint

ENTRYPOINT ["/usr/local/bin/entrypoint"]
