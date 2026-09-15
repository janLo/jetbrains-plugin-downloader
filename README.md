# Jetbrains plugins downloader

This tool allows to mirror all plugins for specified jetbrains products for offline use.
This is intended to provide a way to install and update plugins in environments without
internet access.

# Usage

You can use this tool by just install the python package.
It needs python 3.8 or later!

You need a configuration file. An example is provided. The downloads are based on specific jetbrains
product builds. So you need to know what product builds you're using and reference them in the
configuration file. See below for the details about the build-ids.

## Configuration parameters

* **base_path**: The base path where the plugin description files are stored.
* **storage_path**: The path where the plugin data is stored.
* **base_url**: The url for the plugin description files.
* **storage_url**: The url for the Plugin data.
* **upstream_url**: The upstream for the plugins, usually https://plugins.jetbrains.com.
* **products_url**: The upstream API endpoint to retch recent product builds, usually https://data.services.jetbrains.com/products (optional).
* **versions**: A List of Jetbrains product builds to download plugins for.
* **products**: A list of product specifications to download plugins for (optional, see below).

### Products and versions

The tool uses an API-Endpoint that needs a specific IDE build ID to fetch compatible plugin versions.
These can be specified as a list in the `versions` list in the config file.
The format is specified here: https://plugins.jetbrains.com/docs/marketplace/plugins-list.html and looks like `IU-243.21565.193`.

If you don't want to maintain that list and instead always want to have the plugins for the last `N` major releases downloaded, you can use the `products` list instead.
Each ite of that list is a json object like the following:

```json
{
  "code": "IU",
  "versions": "3",
  "include_rc": true,
  "include_eap": false,
  "use_for_client": false
}
```

This means that for the product with the [code](https://plugins.jetbrains.com/docs/marketplace/product-codes.html) `IU` the build-ids for the last three major releases are fetched.
Each release walks through the lifecycle of being `eap` first, then `rc` and then release.
The `include_{rc,eap}` flags tell the selector if a version should be considered before it's an official release.

The `use_for_client` flag transforms every product build-id to a jetbrains client build id.
That means, for `IU-242.23339.11` it would also emit `JBC-242.23339.11`.
This is necessary if you want plugin definitions specific for the JetBrainsClient, because they're not a standalone product and therefore cannot be queried via the products API.

You can mix `versions` and `products` in your configuration. It will then be just a union of all that will be fetched.

Since IntelliJ IDEA 2025.3, Ultimate and Community are shipped as a single unified
distribution and IntelliJ IDEA Community Edition (`IC`) no longer receives separate releases.
If your configuration uses `"code": "IC"`, switch it to `"code": "IU"` to keep receiving
plugin updates for 2025.3 and later.


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
