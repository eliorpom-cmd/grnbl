# grnbl on a container host: the board always on and the hourly job. Posting to
# WhatsApp stays by hand from the board. data/ must be a persistent volume mounted
# at /app/data; everything else is rebuilt on each deploy. Node is only there for
# the Claude Code CLI.
FROM node:22-slim AS node

FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && npm install -g @anthropic-ai/claude-code@2.1.274 && npm cache clean --force

ENV TZ=Europe/Paris PYTHONUNBUFFERED=1 GRNBL_HOST=0.0.0.0 PORT=8730
WORKDIR /app
COPY . .
EXPOSE 8730
CMD ["/bin/bash", "deploy/serve.sh"]
