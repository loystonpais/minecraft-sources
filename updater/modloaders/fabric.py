import re
from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json
from updater.modloaders.maven import MavenCoord, get_maven_hash

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
FABRIC_MAVEN_BASE = "https://maven.fabricmc.net"


class FabricModloader(BaseModloader):
    """Fabric modloader updater."""

    @property
    def name(self) -> str:
        return "fabric"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/net.fabricmc.fabric-loader/"
        intermediary_url = f"{PRISM_META_BASE}/net.fabricmc.intermediary/"

        logger.info(f"Fetching Fabric Loader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} Fabric versions to {self.raw_dir / 'manifest.json'}")

        logger.info(f"Fetching Fabric Intermediary raw manifest from {intermediary_url}...")
        intermediary_data = fetch_json(intermediary_url)
        save_json(self.raw_dir / "intermediary.json", intermediary_data)
        logger.info(f"Saved {len(intermediary_data.get('versions', []))} Intermediary versions to {self.raw_dir / 'intermediary.json'}")

    def normalize(self) -> None:
        """Generates fabric/versions-list.json, fabric/mappings.json, fabric/loaders.json, and fabric/libraries.json."""
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if not manifest_data:
            return

        raw_versions = manifest_data.get("versions", [])

        # 1. versions-list.json
        versions = [v["version"] for v in raw_versions]
        save_json(self.output_dir / "versions-list.json", versions)
        logger.info(f"Saved {len(versions)} Fabric loader versions to {self.output_dir / 'versions-list.json'}")

        # 2. mappings.json (MC version -> intermediary dependency)
        intermediary_file = self.raw_dir / "intermediary.json"
        intermediary_data = load_json(intermediary_file)
        mappings = {}
        all_required_maven_coords: set[tuple[str, str]] = set()

        if intermediary_data:
            for item in intermediary_data.get("versions", []):
                mc_ver = item.get("version")
                if not mc_ver:
                    continue
                coord_str = f"net.fabricmc:intermediary:{mc_ver}"
                mappings[mc_ver] = {
                    "dependencies": [coord_str]
                }
                all_required_maven_coords.add((coord_str, f"{FABRIC_MAVEN_BASE}/"))
            save_json(self.output_dir / "mappings.json", mappings)
            logger.info(f"Saved {len(mappings)} versions to {self.output_dir / 'mappings.json'}")

        # 3. loaders.json (loader version -> dependencies & mainClass)
        loaders_file = self.output_dir / "loaders.json"
        existing_loaders = load_json(loaders_file) or {}
        loaders: dict[str, dict] = dict(existing_loaders)

        # 4. libraries.json (maven coordinate -> { url, sha256 })
        libraries_file = self.output_dir / "libraries.json"
        existing_libraries = load_json(libraries_file) or {}
        libraries: dict[str, dict] = dict(existing_libraries)

        # We process semver loader releases
        for v_obj in raw_versions:
            ver = v_obj.get("version")
            if not ver or not SEMVER_PATTERN.match(ver):
                continue

            loader_coord = f"net.fabricmc:fabric-loader:{ver}"
            all_required_maven_coords.add((loader_coord, f"{FABRIC_MAVEN_BASE}/"))

            if ver in loaders and loaders[ver].get("dependencies"):
                # Collect libraries from existing cache
                deps = loaders[ver]["dependencies"]
                for dep_list in deps.values():
                    for d in dep_list:
                        all_required_maven_coords.add((d, f"{FABRIC_MAVEN_BASE}/"))
                continue

            try:
                coord = MavenCoord.parse(loader_coord)
                json_url = coord.json_url(FABRIC_MAVEN_BASE)
                loader_spec = fetch_json(json_url, delay=0.02)
                raw_libs = loader_spec.get("libraries", {})

                def extract_names(lib_list):
                    names = []
                    for item in lib_list:
                        name = item.get("name")
                        url = item.get("url", f"{FABRIC_MAVEN_BASE}/")
                        if name:
                            names.append(name)
                            all_required_maven_coords.add((name, url))
                            # If maven json provides sha256 inline, cache it!
                            if "sha256" in item:
                                libraries[name] = {
                                    "url": url,
                                    "sha256": item["sha256"]
                                }
                    return names

                loaders[ver] = {
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
            except Exception as e:
                logger.warning(f"Could not fetch loader spec for Fabric {ver}: {e}")

        save_json(loaders_file, loaders)
        logger.info(f"Saved {len(loaders)} loader versions to {loaders_file}")

        # Resolve hashes for any missing maven coordinates
        missing_coords = [c for c in all_required_maven_coords if c[0] not in libraries]
        if missing_coords:
            logger.info(f"Resolving {len(missing_coords)} library hashes for Fabric...")
            for idx, (coord_str, base_url) in enumerate(missing_coords, 1):
                hash_res = get_maven_hash(coord_str, base_url, existing_cache=libraries)
                if hash_res:
                    h_type, h_val = hash_res
                    libraries[coord_str] = {
                        "url": base_url,
                        h_type: h_val,
                    }
                if idx % 50 == 0:
                    logger.info(f"  [{idx}/{len(missing_coords)}] Resolved library hashes...")

        save_json(libraries_file, libraries)
        logger.info(f"Saved {len(libraries)} libraries to {libraries_file}")

