# Jetbrains plugins downloader

This tool allows to mirror all plugins for specified jetbrains products for offline use.
This is intended to provide a way to install and update plugins in environments without
internet access.

# Usage

You can use this tool by just install the python package.
It needs python 3.8 or later!

You need a configuration file. An example is provided. The downloads are based on specific jetbrains
product builds. So you need to know what product builds you're using and reference them in the
configuration file.

## Configuration parameters

* **base_path**: The base path where the plugin description files are stored.
* **storage_path**: The path where the plugin data is stored.
* **base_url**: The url for the plugin description files.
* **storage_url**: The url for the Plugin data.
* **upstream_url**: The upstream for the plugins, usually https://plugins.jetbrains.com.
* **versions**: A List of Jetbrains product builds to download plugins for.

## Docker image

There is a very basic docker image 
[available](https://hub.docker.com/r/janlo/jetbrains-plugin-downloader). 
You can use it by mounting the file storage
path and the configuration file into the container:

```
docker run \
    -v config.json:/etc/downloader_config.json \
    -v <path-to-file-storage>:/data \
    janlo/jetbrains-plugin-downloader
```
