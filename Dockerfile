FROM python:3-slim-bullseye as builder

ADD . /code

RUN pip install hatch && \
    cd /code && \
    hatch build

FROM python:3-slim-bullseye

COPY --from=builder /code/dist /dist/
COPY config_docker.json /etc/downloader_config.json

RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir /dist/*.whl && \
    mkdir -p /data/files

CMD ["idea-plugin-downloader", "--config-file", "/etc/downloader_config.json"]