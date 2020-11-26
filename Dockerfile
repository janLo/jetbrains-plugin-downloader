FROM python:3

ADD . /code

RUN pip install /code && \
    cp /code/config_docker.json /etc/downloader_config.json && \
    mkdir /data && \
    mkdir /data/files

CMD "idea-plugin-downloader --config-file /etc/downloader_config.json"