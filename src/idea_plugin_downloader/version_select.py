import typing

import httpx
import orjson
import pydantic

_BASE_URL = "https://data.services.jetbrains.com/products"


def build_sort_key(build: str) -> tuple[int, ...]:
    """Turn a dotted build number into a tuple that sorts correctly.

    Non-numeric components (``*``, ``SNAPSHOT``) are treated as "greater than any
    real number" so that e.g. ``253.28294.*`` sorts after ``253.28294.334``.
    """
    key = []
    for part in build.split("."):
        try:
            key.append(int(part))
        except ValueError:
            key.append(2**31 - 1)
    return tuple(key)


class ProductSpec(pydantic.BaseModel):
    code: str
    versions: int = 5
    builds: int = 1
    include_eap: bool = True
    include_rc: bool = True
    use_for_client: bool = False


class VersionSelector:
    def __init__(self, base_url=None):
        self.base_url = base_url or _BASE_URL

        self._session = None
        self._client_versions: dict[str, str] = {}

    @property
    def session(self):
        if self._session is None:
            self._session = httpx.Client()

        return self._session

    def close(self):
        session = self._session
        self._session = None
        if session is not None:
            session.close()

    def fetch_product_versions(self, products: list[ProductSpec]) -> list[str]:
        try:
            return [
                product_id for products_ids in products for product_id in self._fetch_product_version(products_ids)
            ] + list(self._client_versions.values())
        finally:
            self.close()

    def _fetch_product_version(self, product: ProductSpec) -> typing.Iterable[str]:
        allowed_types = {"release"}

        if product.include_rc:
            allowed_types |= {"rc"}

        if product.include_eap:
            allowed_types |= {"eap"}

        resp = self.session.get(self.base_url, params={"code": product.code})
        resp.raise_for_status()
        data = orjson.loads(resp.content)

        # major -> list of (date, build) for every accepted release of that major.
        majors: dict[str, list[tuple[str, str]]] = {}

        for block in data:
            for release in block.get("releases", []):
                if release.get("type") not in allowed_types:
                    continue

                major = release.get("majorVersion")
                if not major:
                    continue

                build = release.get("build", None)
                if not build:
                    continue

                if major not in majors:
                    if len(majors) == product.versions:
                        continue
                    majors[major] = []

                majors[major].append((release.get("date", ""), build))

        builds: list[str] = []
        for major_builds in majors.values():
            # Newest first: sort by date, then by the numeric build id (a release can share a
            # date with another, or the API can omit it).
            major_builds.sort(key=lambda item: (item[0], build_sort_key(item[1])), reverse=True)

            for _date, build in major_builds[: product.builds]:
                builds.append(f"{product.code}-{build}")

                if product.use_for_client:
                    self._client_versions[build] = f"JBC-{build}"

        return sorted(builds, reverse=True)
