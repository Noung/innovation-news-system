FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY scripts/requirements.txt /tmp/requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt

COPY fetch-innovation-news/api/package.json fetch-innovation-news/api/package-lock.json ./fetch-innovation-news/api/
RUN cd fetch-innovation-news/api && npm ci --omit=dev --ignore-scripts

COPY . .
RUN sed -i 's/\r$//' docker/mock/openclaw-mock \
    && chmod 0755 docker/mock/openclaw-mock \
    && mkdir -p cache logs \
    && chown -R node:node /workspace

USER node

EXPOSE 3001

CMD ["node", "fetch-innovation-news/api/server.js"]
