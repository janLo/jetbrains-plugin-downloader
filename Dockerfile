FROM python:3-slim-buster

ADD . /code

RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir /code && \
    cp /code/config_docker.json /etc/downloader_config.json && \
    mkdir -p /data/files

CMD ["idea-plugin-downloader", "--config-file", "/etc/downloader_config.json"]