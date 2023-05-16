import base64
import contextlib
import hashlib
import logging
import pathlib
import re
import shutil
import subprocess
import typing
import urllib.parse
import urllib.request

import click
import pydantic
from defusedxml.ElementTree import parse
from lxml import etree
from lxml.builder import E

_log = logging.getLogger(__name__)


class Config(pydantic.BaseModel):
    base_path: pathlib.Path
    storage_path: pathlib.Path
    base_url: str
    storage_url: str
    upstream_url: str
    versions: list[str]


class PluginEntry(typing.NamedTuple):
    id: str  # noqa A003
    version: str


class PluginSpec(typing.NamedTuple):
    entry: PluginEntry
    name: str
    description: str
    idea_version: dict[str, str]


def _escape_path(path) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.md5(path.encode("utf-8")).digest())  # noqa S324
        .decode("utf-8")
        .replace("=", "")
    )


class StorageManager:
    def __init__(self, storage_path: pathlib.Path):
        self._storage = storage_path

    def plugin_dir(self, plugin_entry: PluginEntry) -> pathlib.Path:
        return pathlib.Path(_escape_path(plugin_entry.id)) / _escape_path(plugin_entry.version)

    def plugin_exists(self, plugin_entry: PluginEntry) -> bool:
        return (self._storage / self.plugin_dir(plugin_entry)).exists()

    def plugin_filename(self, plugin_entry: PluginEntry) -> str | None:
        for entry in (self._storage / self.plugin_dir(plugin_entry)).iterdir():
            if entry.is_file():
                return entry.name
        return None

    def create_plugin_path(self, plugin_entry: PluginEntry) -> pathlib.Path:
        target = self._storage / self.plugin_dir(plugin_entry)
        target.mkdir(parents=True, exist_ok=True)
        return target

    @contextlib.contextmanager
    def plugin_backup(self, plugin_entry: PluginEntry) -> pathlib.Path:
        path = self.create_plugin_path(plugin_entry)

        old_file = self.plugin_filename(plugin_entry)
        if old_file is not None:
            target_file = path / old_file
            backup_path = target_file.with_suffix(".1")
            target_file.rename(backup_path)

            try:
                yield path
            except:  # noqa
                if target_file.exists():
                    target_file.unlink()
                backup_path.rename(target_file)
            else:
                backup_path.unlink()

            return

        yield path

    def cleanup_plugin(self, plugin_entry_list: list[PluginEntry]):
        plugin_set = {_escape_path(entry.id) for entry in plugin_entry_list}
        version_set = {(_escape_path(entry.id), _escape_path(entry.version)) for entry in plugin_entry_list}

        to_delete = []

        for plugin_dir in self._storage.iterdir():
            if not plugin_dir.is_dir():
                _log.debug("No plugin directory: %s", plugin_dir)
                continue

            if plugin_dir.name not in plugin_set:
                _log.debug("Plugins in plugin dir %s are not used in any xml", plugin_dir)
                to_delete.append(plugin_dir)
                continue

            versions = 0
            for version_dir in plugin_dir.iterdir():
                versions += 1

                if (plugin_dir.name, version_dir.name) not in version_set:
                    _log.debug("Plugin version in dir %s is not used in any plugin xml", version_dir)
                    to_delete.append(version_dir)
                    continue

                if next(iter(version_dir.iterdir()), None) is None:
                    _log.debug("Plugin version dir %s is empty", version_dir)
                    to_delete.append(version_dir)

            if 0 == versions:
                _log.debug("Plugin dir %s is empty", plugin_dir)
                to_delete.append(plugin_dir)

        for entry in to_delete:
            _log.info("Delete plugin dir %s", entry)
            shutil.rmtree(entry)


class DownloadManager:
    def __init__(self, base_url: str):
        self._base_url = base_url

    def download_plugin(self, plugin_entry: PluginEntry, target_path: pathlib.Path):
        params = urllib.parse.urlencode({"pluginId": plugin_entry.id, "version": plugin_entry.version})

        url = f"{self._base_url}/plugin/download?{params}"

        _log.info("Download plugin %s from %s to %s", plugin_entry.id, url, target_path)

        curl_command = [
            "/usr/bin/curl",
            "--remote-name",
            "--remote-header-name",
            "--location",
            "--silent",
            "--show-error",
            url,
        ]

        _log.debug(
            "Download plugin %s in version %s using the command %s",
            plugin_entry.id,
            plugin_entry.version,
            curl_command,
        )

        proc = subprocess.Popen(
            curl_command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, cwd=target_path  # noqa S603
        )
        proc.wait()

        if proc.returncode != 0:
            _log.warning(
                "Could not download from %s - ignore plugin %s:\n%s",
                url,
                plugin_entry.id,
                proc.stderr.read(),
            )
            return False
        else:
            _log.debug(
                "Output from %s (exit: %d):\nstdout:\n%s\nstderr:\n%s",
                curl_command,
                proc.returncode,
                proc.stdout.read().decode("utf-8"),
                proc.stderr.read().decode("utf-8"),
            )

        return True


class PluginFileManager:
    def __init__(self, base_path: pathlib.Path, base_url: str, storage_url: str, storage: StorageManager):
        self._base_path = base_path
        self._base_url = base_url
        self._storage_url = storage_url
        self._storage = storage

        self._regex = re.compile(r"^(?P<tool>[A-Z]+)-(?P<version>[0-9]+)\..*$")

        if not self._storage_url.endswith("/"):
            self._storage_url += "/"

    def url_for(self, plugin_entry: PluginEntry) -> str | None:
        fpath = self._storage.plugin_filename(plugin_entry)
        if fpath is None:
            _log.warning(
                "Cannot find a file in entry directory %s for version %s",
                plugin_entry.id,
                plugin_entry.version,
            )
            return None

        path = self._storage.plugin_dir(plugin_entry) / fpath
        return urllib.parse.urljoin(self._storage_url, str(path))

    def create_for(self, build_id: str, plugin_list: list[PluginSpec]):
        match = self._regex.match(build_id)
        if match is None:
            msg = f"Could not recognize build id {build_id}"
            raise AssertionError(msg)

        tool = match.group("tool")
        version = match.group("version")

        xml_path = self._base_path / f"plugins-{tool}-{version}.xml"

        logging.info(
            "Create plugin file for build %s with %d entries in file %s",
            build_id,
            len(plugin_list),
            xml_path,
        )

        entry_urls = [(item, self.url_for(item.entry)) for item in plugin_list]

        res = E.plugins(
            *[
                E.plugin(
                    E.idea_version(dict(item.idea_version)),
                    E.name(item.name),
                    {
                        "id": item.entry.id,
                        "url": self.url_for(item.entry),
                        "version": item.entry.version,
                    },
                )
                for item, url in entry_urls
                if url is not None
            ]
        )

        with xml_path.open("wb") as fh:
            fh.write(etree.tostring(res, pretty_print=True))


class PluginManager:
    def __init__(
        self,
        base_url: str,
        storage: StorageManager,
        downloader: DownloadManager,
        plugin_file_manager: PluginFileManager,
    ):
        self._base_url = base_url
        self._storage = storage
        self._downloader = downloader
        self._plugin_fm = plugin_file_manager

        self._plugins = set()  # type: typing.Set[PluginEntry]
        self._builds = []

    def list_plugins_for(self, build_id):
        url = f"{self._base_url}/plugins/list/?build={build_id}"
        tree = parse(urllib.request.urlopen(url))  # noqa S603

        _log.info("Loaded plugin-list for %s from %s", build_id, url)

        for plugin_item in tree.iterfind(".//idea-plugin"):
            try:
                yield PluginSpec(
                    entry=PluginEntry(
                        id=plugin_item.find("id").text,
                        version=plugin_item.find("version").text,
                    ),
                    description=plugin_item.find("description").text,
                    name=plugin_item.find("name").text,
                    idea_version=dict(plugin_item.find("idea-version").attrib),
                )
            except:  # noqa
                _log.exception("Cannot parse entry %s", plugin_item)

    def download_for(self, build_id: str, included=None):
        processed = []

        for plugin_spec in self.list_plugins_for(build_id=build_id):
            if included and plugin_spec.entry.id not in included:
                continue

            _log.debug(
                "Plugin %s in version %s requested for build %s",
                plugin_spec.entry.id,
                plugin_spec.entry.version,
                build_id,
            )

            if plugin_spec.entry not in self._plugins and not self._storage.plugin_exists(plugin_spec.entry):
                with self._storage.plugin_backup(plugin_spec.entry) as target_path:
                    if not self._downloader.download_plugin(plugin_entry=plugin_spec.entry, target_path=target_path):
                        continue
            else:
                _log.info(
                    "Plugin %s in version %s already downloaded.",
                    plugin_spec.entry.id,
                    plugin_spec.entry.version,
                )
            processed.append(plugin_spec)
            self._plugins.add(plugin_spec.entry)

        self._plugin_fm.create_for(build_id=build_id, plugin_list=processed)

    def cleanup_old(self):
        _log.info("Cleanup old plugins")
        self._storage.cleanup_plugin(list(self._plugins))


@click.command("idea-plugin-downloader")
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    help="Path to the config file",
    required=True,
    envvar="DL_CONFIG_FILE",
)
@click.option(
    "--log-level",
    type=click.Choice(choices=["DEBUG", "INFO", "WARNING"]),
    help="Set the log-level",
    default="WARNING",
    envvar="DL_LOG_LEVEL",
)
@click.option(
    "--include-plugin",
    multiple=True,
    help="Select plugin ids to include (can be repeated)",
)
def main(config_file, log_level, include_plugin):
    logging.basicConfig(level=getattr(logging, log_level))
    config = Config.parse_file(config_file)

    sm = StorageManager(storage_path=config.storage_path)
    dm = DownloadManager(base_url=config.upstream_url)
    pfm = PluginFileManager(
        base_path=config.base_path,
        base_url=config.base_url,
        storage_url=config.storage_url,
        storage=sm,
    )
    pm = PluginManager(base_url=config.upstream_url, storage=sm, downloader=dm, plugin_file_manager=pfm)

    for build_id in config.versions:
        _log.info("Process plugins for build %s", build_id)
        pm.download_for(build_id=build_id, included=include_plugin)

    pm.cleanup_old()

    return 0
