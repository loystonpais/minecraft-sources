import re
from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json
from updater.modloaders.maven import MavenCoord, get_maven_hash

SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+")
QUILT_MAVEN_BASE = "https://maven.quiltmc.org/repository/release"
FABRIC_MAVEN_BASE = "https://maven.fabricmc.net"


class QuiltModloader(BaseModloader):
    """Quilt modloader updater."""

    QUILT_META_BASE = "https://meta.quiltmc.org/v3/versions"

    @property
    def name(self) -> str:
        return "quilt"

    def update_raw(self) -> None:
        loader_url = f"{self.QUILT_META_BASE}/loader"
        hashed_url = f"{self.QUILT_META_BASE}/hashed"
        intermediary_url = f"{self.QUILT_META_BASE}/intermediary"

        logger.info(f"Fetching Quilt Loader raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data)} Quilt versions to {self.raw_dir / 'manifest.json'}")

        logger.info(f"Fetching Quilt hashed mappings from {hashed_url}...")
        hashed_data = fetch_json(hashed_url)
        save_json(self.raw_dir / "hashed.json", hashed_data)
        logger.info(f"Saved {len(hashed_data)} Quilt hashed versions to {self.raw_dir / 'hashed.json'}")

        logger.info(f"Fetching Quilt intermediary mappings from {intermediary_url}...")
        intermediary_data = fetch_json(intermediary_url)
        save_json(self.raw_dir / "intermediary.json", intermediary_data)
        logger.info(f"Saved {len(intermediary_data)} Quilt intermediary versions to {self.raw_dir / 'intermediary.json'}")

    def normalize(self) -> None:
        """Generates quilt/versions-list.json, quilt/mappings.json, quilt/loaders.json, and quilt/libraries.json."""
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if not manifest_data:
            return

        raw_versions = manifest_data if isinstance(manifest_data, list) else manifest_data.get("versions", [])

        # 1. versions-list.json
        versions = [v["version"] for v in raw_versions]
        save_json(self.output_dir / "versions-list.json", versions)
        logger.info(f"Saved {len(versions)} Quilt loader versions to {self.output_dir / 'versions-list.json'}")

        # 2. mappings.json (mapping MC version -> intermediary & hashed dependencies)
        hashed_file = self.raw_dir / "hashed.json"
        hashed_data = load_json(hashed_file) or []

        intermediary_file = self.raw_dir / "intermediary.json"
        intermediary_data = load_json(intermediary_file) or []

        mappings: dict[str, dict[str, list[str]]] = {}
        all_required_maven_coords: set[tuple[str, str]] = set()

        # 3. libraries.json
        libraries_file = self.output_dir / "libraries.json"
        existing_libraries = load_json(libraries_file) or {}
        libraries: dict[str, dict] = dict(existing_libraries)

        # Intermediary mappings
        for item in intermediary_data:
            mc_ver = item.get("version")
            maven = item.get("maven")
            if mc_ver and maven:
                if mc_ver not in mappings:
                    mappings[mc_ver] = {"dependencies": []}
                if maven not in mappings[mc_ver]["dependencies"]:
                    mappings[mc_ver]["dependencies"].append(maven)
                all_required_maven_coords.add((maven, f"{FABRIC_MAVEN_BASE}/"))

        # Hashed mappings (provide sha256 inline from Quilt API!)
        for item in hashed_data:
            mc_ver = item.get("version")
            maven = item.get("maven")
            if mc_ver and maven:
                if mc_ver not in mappings:
                    mappings[mc_ver] = {"dependencies": []}
                if maven not in mappings[mc_ver]["dependencies"]:
                    mappings[mc_ver]["dependencies"].append(maven)
                all_required_maven_coords.add((maven, f"{QUILT_MAVEN_BASE}/"))
                hashes = item.get("hashes", {})
                if "sha256" in hashes:
                    full_url = MavenCoord.parse(maven).jar_url(f"{QUILT_MAVEN_BASE}/")
                    libraries[maven] = {
                        "url": full_url,
                        "sha256": hashes["sha256"]
                    }

        save_json(self.output_dir / "mappings.json", mappings)
        logger.info(f"Saved {len(mappings)} versions to {self.output_dir / 'mappings.json'}")

        # 4. loaders.json (loader version -> dependencies & mainClass)
        loaders_file = self.output_dir / "loaders.json"
        existing_loaders = load_json(loaders_file) or {}
        loaders: dict[str, dict] = dict(existing_loaders)

        for v_obj in raw_versions:
            ver = v_obj.get("version")
            if not ver or not SEMVER_PATTERN.match(ver):
                continue

            loader_coord = f"org.quiltmc:quilt-loader:{ver}"
            # Quilt API provides loader sha256 directly in the manifest
            hashes = v_obj.get("hashes", {})
            if "sha256" in hashes:
                libraries[loader_coord] = {
                    "url": MavenCoord.parse(loader_coord).jar_url(f"{QUILT_MAVEN_BASE}/"),
                    "sha256": hashes["sha256"]
                }

            if ver in loaders and loaders[ver].get("dependencies"):
                deps = loaders[ver]["dependencies"]
                # Only skip if all dependencies are already present in libraries.json
                all_deps = [d for group in deps.values() for d in group]
                if all(d in libraries for d in all_deps):
                    continue

            try:
                coord = MavenCoord.parse(loader_coord)
                json_url = coord.json_url(QUILT_MAVEN_BASE)
                loader_spec = fetch_json(json_url, delay=0.02)
                raw_libs = loader_spec.get("libraries", {})

                def extract_names(lib_list):
                    names = []
                    for item in lib_list:
                        name = item.get("name")
                        base = item.get("url") or f"{QUILT_MAVEN_BASE}/"
                        if name:
                            names.append(name)
                            if name not in libraries:
                                if "sha256" in item:
                                    libraries[name] = {
                                        "url": MavenCoord.parse(name).jar_url(base),
                                        "sha256": item["sha256"]
                                    }
                                else:
                                    hash_res = get_maven_hash(name, base, existing_cache=libraries)
                                    if hash_res:
                                        h_type, h_val = hash_res
                                        libraries[name] = {
                                            "url": MavenCoord.parse(name).jar_url(base),
                                            h_type: h_val
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
                        "client": "org.quiltmc.loader.impl.launch.knot.KnotClient",
                        "server": "org.quiltmc.loader.impl.launch.knot.KnotServer"
                    })
                }
            except Exception as e:
                logger.warning(f"Could not fetch loader spec for Quilt {ver}: {e}")

        save_json(loaders_file, loaders)
        logger.info(f"Saved {len(loaders)} loader versions to {loaders_file}")
        save_json(libraries_file, libraries)
        logger.info(f"Saved {len(libraries)} libraries to {libraries_file}")


