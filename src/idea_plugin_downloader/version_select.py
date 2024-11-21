import typing

import httpx
import orjson
import pydantic

_BASE_URL = "https://data.services.jetbrains.com/products"


class ProductSpec(pydantic.BaseModel):
    code: str
    versions: int = 5
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

        versions = {}

        for block in data:
            for release in block.get("releases", []):
                if len(versions) == product.versions:
                    break

                if release.get("type") not in allowed_types:
                    continue

                version = release.get("version", None)

                if not version:
                    continue

                if version in versions:
                    continue

                if version != release.get("majorVersion"):
                    continue

                build = release.get("build", None)
                if not build:
                    continue

                versions[version] = f"{product.code}-{build}"

                if product.use_for_client and version not in self._client_versions:
                    self._client_versions[version] = f"JBC-{build}"

        return sorted(versions.values(), reverse=True)
