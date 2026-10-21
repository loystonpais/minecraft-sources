from collections import defaultdict
from updater.modloaders.base import BaseModloader
from updater.config import PRISM_META_BASE, save_json, load_json, logger
from updater.fetch import fetch_json


class ForgeModloader(BaseModloader):
    """Minecraft Forge updater."""

    @property
    def name(self) -> str:
        return "forge"

    def update_raw(self) -> None:
        loader_url = f"{PRISM_META_BASE}/net.minecraftforge/"

        logger.info(f"Fetching Forge raw manifest from {loader_url}...")
        loader_data = fetch_json(loader_url)
        save_json(self.raw_dir / "manifest.json", loader_data)
        logger.info(f"Saved {len(loader_data.get('versions', []))} Forge versions to {self.raw_dir / 'manifest.json'}")

    def normalize(self) -> None:
        """Generates forge/versions.json, forge/versions-list.json, forge/loaders.json, and forge/libraries.json."""
        manifest_file = self.raw_dir / "manifest.json"
        manifest_data = load_json(manifest_file)
        if not manifest_data:
            return

        raw_versions = manifest_data.get("versions", [])
        versions_list = [v["version"] for v in raw_versions]
        save_json(self.output_dir / "versions-list.json", versions_list)
        logger.info(f"Saved {len(versions_list)} Forge versions to {self.output_dir / 'versions-list.json'}")

        # 1. Index by Minecraft version
        by_game_version: dict[str, list[dict]] = defaultdict(list)
        for v in raw_versions:
            forge_ver = v.get("version")
            requires = v.get("requires", [])
            mc_ver = None
            for req in requires:
                if req.get("uid") == "net.minecraft":
                    mc_ver = req.get("equals")
                    break

            if not mc_ver:
                continue

            by_game_version[mc_ver].append({
                "version": forge_ver,
                "releaseTime": v.get("releaseTime"),
                "recommended": v.get("recommended", False),
                "sha256": v.get("sha256"),
            })

        save_json(self.output_dir / "versions.json", dict(by_game_version))
        logger.info(f"Saved Forge versions for {len(by_game_version)} MC versions to {self.output_dir / 'versions.json'}")

        # 2. Pick recommended build (or latest if no recommended) per MC version
        selected_versions: list[str] = []
        for mc_ver, v_list in by_game_version.items():
            rec = next((v for v in v_list if v.get("recommended")), None)
            selected = rec if rec else v_list[0]
            selected_versions.append(selected["version"])

        # 3. Load existing caches
        loaders_file = self.output_dir / "loaders.json"
        existing_loaders = load_json(loaders_file) or {}
        loaders: dict[str, dict] = dict(existing_loaders)

        libraries_file = self.output_dir / "libraries.json"
        existing_libraries = load_json(libraries_file) or {}
        libraries: dict[str, dict] = dict(existing_libraries)

        # 4. Fetch component spec for selected builds
        pending_versions = [
            ver for ver in selected_versions
            if not (
                ver in loaders
                and loaders[ver].get("dependencies")
                and "installer" in loaders[ver]
                and (
                    not loaders[ver].get("installer")
                    or any("binarypatcher" in d for d in loaders[ver].get("dependencies", []))
                )
            )
        ]

        if pending_versions:
            from concurrent.futures import ThreadPoolExecutor
            logger.info(f"Fetching {len(pending_versions)} Forge loader specs in parallel...")

            def process_forge(ver):
                comp_url = f"{PRISM_META_BASE}/net.minecraftforge/{ver}.json"
                spec = fetch_json(comp_url, delay=0.0)
                raw_libs = spec.get("libraries", [])

                dep_names = []
                discovered_libs = {}
                for lib_entry in raw_libs:
                    name = lib_entry.get("name")
                    if not name:
                        continue
                    dep_names.append(name)

                    dl = lib_entry.get("downloads", {}).get("artifact", {})
                    url = dl.get("url") or lib_entry.get("url")
                    sha1 = dl.get("sha1") or lib_entry.get("sha1")
                    sha256 = dl.get("sha256") or lib_entry.get("sha256")

                    if url and (sha1 or sha256):
                        entry = {"url": url}
                        if sha256:
                            entry["sha256"] = sha256
                        if sha1:
                            entry["sha1"] = sha1
                        discovered_libs[name] = entry

                installer_coord = None
                for mf in spec.get("mavenFiles", []):
                    mf_name = mf.get("name")
                    if not mf_name:
                        continue
                    dl = mf.get("downloads", {}).get("artifact", {})
                    url = dl.get("url") or mf.get("url") or ""
                    is_installer = mf_name.endswith(":installer") or "-installer.jar" in url
                    if is_installer:
                        installer_coord = mf_name
                    elif mf_name not in dep_names:
                        dep_names.append(mf_name)

                    sha1 = dl.get("sha1") or mf.get("sha1")
                    sha256 = dl.get("sha256") or mf.get("sha256")
                    if url and (sha1 or sha256):
                        entry = {"url": url}
                        if sha256:
                            entry["sha256"] = sha256
                        if sha1:
                            entry["sha1"] = sha1
                        discovered_libs[mf_name] = entry

                res = {
                    "version": ver,
                    "dependencies": dep_names,
                    "mainClass": spec.get("mainClass"),
                    "installer": installer_coord,
                    "minecraftArguments": spec.get("minecraftArguments"),
                }
                return ver, res, discovered_libs

            with ThreadPoolExecutor(max_workers=16) as pool:
                results = list(pool.map(process_forge, pending_versions))

            for ver, res, discovered_libs in results:
                loaders[ver] = res
                libraries.update(discovered_libs)

        save_json(loaders_file, loaders)
        logger.info(f"Saved {len(loaders)} loader versions to {loaders_file}")

        save_json(libraries_file, libraries)
        logger.info(f"Saved {len(libraries)} libraries to {libraries_file}")
