import re
from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json
from updater.modloaders.maven import MavenCoord, get_maven_hash

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
FABRIC_MAVEN_BASE = "https://maven.fabricmc.net"


class FabricModloader(BaseModloader):
    """Fabric modloader updater."""

    FABRIC_META_BASE = "https://meta.fabricmc.net/v2/versions"

    @property
    def name(self) -> str:
        return "fabric"

    def update_raw(self) -> None:
        loader_url = f"{self.FABRIC_META_BASE}/loader"
        intermediary_url = f"{self.FABRIC_META_BASE}/intermediary"

        logger.info(f"Fetching Fabric Loader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data)} Fabric versions to {self.raw_dir / 'manifest.json'}")

        logger.info(f"Fetching Fabric Intermediary raw manifest from {intermediary_url}...")
        intermediary_data = fetch_json(intermediary_url)
        save_json(self.raw_dir / "intermediary.json", intermediary_data)
        logger.info(f"Saved {len(intermediary_data)} Intermediary versions to {self.raw_dir / 'intermediary.json'}")

    def normalize(self) -> None:
        """Generates fabric/versions-list.json, fabric/mappings.json, fabric/loaders.json, and fabric/libraries.json."""
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if not manifest_data:
            return

        raw_versions = manifest_data if isinstance(manifest_data, list) else manifest_data.get("versions", [])

        # 1. versions-list.json
        versions = [v["version"] for v in raw_versions]
        save_json(self.output_dir / "versions-list.json", versions)
        logger.info(f"Saved {len(versions)} Fabric loader versions to {self.output_dir / 'versions-list.json'}")

        # 2. mappings.json (MC version -> intermediary dependency)
        intermediary_file = self.raw_dir / "intermediary.json"
        intermediary_data = load_json(intermediary_file) or []
        mappings = {}

        # 3. libraries.json (maven coordinate -> { url, sha256 })
        libraries_file = self.output_dir / "libraries.json"
        existing_libraries = load_json(libraries_file) or {}
        libraries: dict[str, dict] = dict(existing_libraries)

        items = intermediary_data if isinstance(intermediary_data, list) else intermediary_data.get("versions", [])
        missing_intermediary = []
        for item in items:
            mc_ver = item.get("version")
            if not mc_ver:
                continue
            coord_str = item.get("maven") or f"net.fabricmc:intermediary:{mc_ver}"
            mappings[mc_ver] = {
                "dependencies": [coord_str]
            }
            if coord_str not in libraries:
                missing_intermediary.append(coord_str)

        if missing_intermediary:
            from concurrent.futures import ThreadPoolExecutor
            logger.info(f"Resolving {len(missing_intermediary)} intermediary library hashes in parallel...")
            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(lambda c: (c, get_maven_hash(c, f"{FABRIC_MAVEN_BASE}/", existing_cache=libraries)), missing_intermediary))
            for coord_str, hash_res in results:
                if hash_res:
                    h_type, h_val = hash_res
                    libraries[coord_str] = {
                        "url": MavenCoord.parse(coord_str).jar_url(f"{FABRIC_MAVEN_BASE}/"),
                        h_type: h_val,
                    }

        save_json(self.output_dir / "mappings.json", mappings)
        logger.info(f"Saved {len(mappings)} versions to {self.output_dir / 'mappings.json'}")

        # 4. loaders.json (loader version -> dependencies & mainClass)
        loaders_file = self.output_dir / "loaders.json"
        existing_loaders = load_json(loaders_file) or {}
        loaders: dict[str, dict] = dict(existing_loaders)

        # Collect loader versions that need processing
        pending_versions = []
        for v_obj in raw_versions:
            ver = v_obj.get("version")
            if not ver or not SEMVER_PATTERN.match(ver):
                continue

            loader_coord = v_obj.get("maven") or f"net.fabricmc:fabric-loader:{ver}"
            if ver in loaders and loaders[ver].get("dependencies"):
                deps = loaders[ver]["dependencies"]
                all_deps = [d for group in deps.values() for d in group]
                if all(d in libraries for d in all_deps) and loader_coord in libraries:
                    continue

            pending_versions.append((ver, loader_coord))

        if pending_versions:
            from concurrent.futures import ThreadPoolExecutor
            logger.info(f"Processing {len(pending_versions)} Fabric loader specs in parallel...")

            def process_fabric_loader(item_pair):
                ver, loader_coord = item_pair
                discovered_libs: dict[str, dict] = {}

                if loader_coord not in libraries:
                    hash_res = get_maven_hash(loader_coord, f"{FABRIC_MAVEN_BASE}/", existing_cache=libraries)
                    if hash_res:
                        h_type, h_val = hash_res
                        discovered_libs[loader_coord] = {
                            "url": MavenCoord.parse(loader_coord).jar_url(f"{FABRIC_MAVEN_BASE}/"),
                            h_type: h_val,
                        }

                coord = MavenCoord.parse(loader_coord)
                json_url = coord.json_url(FABRIC_MAVEN_BASE)
                loader_spec = fetch_json(json_url, delay=0.0)
                raw_libs = loader_spec.get("libraries", {})

                def extract_names(lib_list):
                    names = []
                    for item in lib_list:
                        name = item.get("name")
                        base = item.get("url") or f"{FABRIC_MAVEN_BASE}/"
                        if name:
                            names.append(name)
                            if name not in libraries and name not in discovered_libs:
                                if "sha256" in item:
                                    discovered_libs[name] = {
                                        "url": MavenCoord.parse(name).jar_url(base),
                                        "sha256": item["sha256"]
                                    }
                                else:
                                    hash_res = get_maven_hash(name, base, existing_cache=libraries)
                                    if hash_res:
                                        h_type, h_val = hash_res
                                        discovered_libs[name] = {
                                            "url": MavenCoord.parse(name).jar_url(base),
                                            h_type: h_val
                                        }
                    return names

                res_loader = {
                    "name": loader_coord,
                    "dependencies": {
                        "client": extract_names(raw_libs.get("client", [])),
                        "common": extract_names(raw_libs.get("common", [])),
                        "server": extract_names(raw_libs.get("server", [])),
                    },
                    "mainClass": loader_spec.get("mainClass", {
                        "client": "net.fabricmc.loader.impl.launch.knot.KnotClient",
                        "server": "net.fabricmc.loader.impl.launch.knot.KnotServer"
                    })
                }
                return ver, res_loader, discovered_libs

            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(process_fabric_loader, pending_versions))

            for ver, res_loader, discovered_libs in results:
                loaders[ver] = res_loader
                libraries.update(discovered_libs)

        save_json(loaders_file, loaders)
        logger.info(f"Saved {len(loaders)} loader versions to {loaders_file}")
        save_json(libraries_file, libraries)
        logger.info(f"Saved {len(libraries)} libraries to {libraries_file}")


