FROM python:3-slim-buster

ADD . /code

RUN apt update && \
    apt install -y curl && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN pip install /code && \
    cp /code/config_docker.json /etc/downloader_config.json && \
    mkdir /data && \
    mkdir /data/files

CMD "idea-plugin-downloader --config-file /etc/downloader_config.json"