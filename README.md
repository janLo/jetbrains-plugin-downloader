# Jetbrains plugins downloader

This tool allows to mirror all plugins for specified jetbrains products for offline use.
This is intended to provide a way to install and update plugins in environments without
internet access.

# Usage

You can use this tool by just install the pytjon Package.
It needs python 3.8 or later!

You need a config-file. An example is provided. The downloads are based on specific jetbrains
product builds. So you need to know what product builds you're using and refernece them in the
config.

## Docker-Image

There is a very basic docker image available. You can use it by mounting the file storage
path and the configuration file into the container:

```
docker run \
    -v config.json:/etc/downloader_config.json \
    -v <path-to-file-storage>:/data \
    janlo/jetbrains-plugin-downloader
```