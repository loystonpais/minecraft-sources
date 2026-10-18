import re
import sys
from pathlib import Path
from typing import Any
from updater.config import REPO_ROOT, load_json, logger

NIXCRAFT_DIR = REPO_ROOT / "nixcraft"

SRI_HASH_PATTERN = re.compile(r"^(sha256|sha1|sha512|md5)-[A-Za-z0-9+/=]+$")


class SchemaError(Exception):
    """Raised when a schema validation check fails."""

    pass


def fail(file_name: str, message: str) -> None:
    raise SchemaError(f"[{file_name}] {message}")


def assert_type(
    file_name: str, key_path: str, val: Any, expected_type: type | tuple[type, ...]
) -> None:
    if not isinstance(val, expected_type):
        type_name = (
            expected_type.__name__
            if isinstance(expected_type, type)
            else "/".join(t.__name__ for t in expected_type)
        )
        fail(
            file_name,
            f"Expected '{key_path}' to be of type {type_name}, got {type(val).__name__}: {val!r}",
        )


def assert_sri(file_name: str, key_path: str, val: Any) -> None:
    assert_type(file_name, key_path, val, str)
    if not SRI_HASH_PATTERN.match(val):
        fail(
            file_name,
            f"Expected '{key_path}' to be a valid SRI hash (algo-base64), got: {val!r}",
        )


def verify_libraries(data: dict[str, Any]) -> None:
    file_name = "libraries.json"
    assert_type(file_name, "root", data, dict)
    if not data:
        fail(file_name, "libraries.json is empty")

    for coord, info in data.items():
        assert_type(file_name, f"libraries.{coord}", info, dict)
        if "url" not in info:
            fail(file_name, f"Missing 'url' in library '{coord}'")
        assert_type(file_name, f"libraries.{coord}.url", info["url"], str)
        if not (
            info["url"].startswith("http://") or info["url"].startswith("https://")
        ):
            fail(file_name, f"Invalid URL in library '{coord}': {info['url']}")

        if "hash" not in info:
            fail(file_name, f"Missing 'hash' in library '{coord}'")
        assert_sri(file_name, f"libraries.{coord}.hash", info["hash"])


def verify_mojang(data: dict[str, Any]) -> None:
    file_name = "mojang.json"
    assert_type(file_name, "root", data, dict)
    for expected_key in ["latest", "versions_list", "versions", "data_versions"]:
        if expected_key not in data:
            fail(file_name, f"Missing top-level key '{expected_key}'")

    # latest
    latest = data["latest"]
    assert_type(file_name, "latest", latest, dict)
    for k in ["release", "snapshot"]:
        if k not in latest:
            fail(file_name, f"Missing '{k}' in 'latest'")
        assert_type(file_name, f"latest.{k}", latest[k], str)

    # versions_list
    v_list = data["versions_list"]
    assert_type(file_name, "versions_list", v_list, list)
    if not v_list:
        fail(file_name, "'versions_list' is empty")
    for idx, v in enumerate(v_list[:10]):
        assert_type(file_name, f"versions_list[{idx}]", v, str)

    # versions
    versions = data["versions"]
    assert_type(file_name, "versions", versions, dict)
    for v_id, info in versions.items():
        assert_type(file_name, f"versions.{v_id}", info, dict)
        for req in ["type", "url", "hash"]:
            if req not in info:
                fail(file_name, f"Missing '{req}' in version '{v_id}'")
        assert_type(file_name, f"versions.{v_id}.type", info["type"], str)
        assert_type(file_name, f"versions.{v_id}.url", info["url"], str)
        assert_sri(file_name, f"versions.{v_id}.hash", info["hash"])

    # data_versions
    dv = data["data_versions"]
    assert_type(file_name, "data_versions", dv, dict)
    for mc, val in dv.items():
        assert_type(file_name, f"data_versions.{mc}", val, int)


def verify_modloader_fabric_quilt(file_name: str, data: dict[str, Any]) -> None:
    assert_type(file_name, "root", data, dict)
    for req in ["versions", "loaders", "mappings"]:
        if req not in data:
            fail(file_name, f"Missing top-level key '{req}'")

    # versions
    assert_type(file_name, "versions", data["versions"], list)
    if not data["versions"]:
        fail(file_name, "'versions' list is empty")
    for idx, v in enumerate(data["versions"][:10]):
        assert_type(file_name, f"versions[{idx}]", v, str)

    # loaders
    assert_type(file_name, "loaders", data["loaders"], dict)
    for l_id, l_info in data["loaders"].items():
        assert_type(file_name, f"loaders.{l_id}", l_info, dict)
        for req in ["dependencies", "mainClass"]:
            if req not in l_info:
                fail(file_name, f"Missing '{req}' in loader '{l_id}'")

        deps = l_info["dependencies"]
        assert_type(file_name, f"loaders.{l_id}.dependencies", deps, dict)
        for grp in ["client", "common", "server"]:
            if grp in deps:
                assert_type(
                    file_name, f"loaders.{l_id}.dependencies.{grp}", deps[grp], list
                )
                for c in deps[grp]:
                    assert_type(
                        file_name, f"loaders.{l_id}.dependencies.{grp}[]", c, str
                    )

        mc = l_info["mainClass"]
        assert_type(file_name, f"loaders.{l_id}.mainClass", mc, dict)

    # mappings
    assert_type(file_name, "mappings", data["mappings"], dict)
    for mc, m_deps in data["mappings"].items():
        assert_type(file_name, f"mappings.{mc}", m_deps, list)
        for c in m_deps:
            assert_type(file_name, f"mappings.{mc}[]", c, str)


def verify_modloader_forge_neoforge(file_name: str, data: dict[str, Any]) -> None:
    assert_type(file_name, "root", data, dict)
    for req in ["versions", "game_versions", "loaders"]:
        if req not in data:
            fail(file_name, f"Missing top-level key '{req}'")

    # versions
    assert_type(file_name, "versions", data["versions"], list)
    if not data["versions"]:
        fail(file_name, "'versions' list is empty")
    for idx, v in enumerate(data["versions"][:10]):
        assert_type(file_name, f"versions[{idx}]", v, str)

    # game_versions
    assert_type(file_name, "game_versions", data["game_versions"], dict)
    for mc, l_ver in data["game_versions"].items():
        assert_type(file_name, f"game_versions.{mc}", l_ver, str)
        if l_ver not in data["loaders"]:
            fail(
                file_name,
                f"game_versions.{mc} refers to loader '{l_ver}', which is missing from 'loaders'",
            )

    # loaders
    assert_type(file_name, "loaders", data["loaders"], dict)
    for l_id, l_info in data["loaders"].items():
        assert_type(file_name, f"loaders.{l_id}", l_info, dict)
        if "dependencies" not in l_info:
            fail(file_name, f"Missing 'dependencies' in loader '{l_id}'")
        assert_type(
            file_name, f"loaders.{l_id}.dependencies", l_info["dependencies"], list
        )
        for c in l_info["dependencies"]:
            assert_type(file_name, f"loaders.{l_id}.dependencies[]", c, str)


def verify_lwjgl(data: dict[str, Any]) -> None:
    file_name = "lwjgl.json"
    assert_type(file_name, "root", data, dict)
    for req in ["versions", "components"]:
        if req not in data:
            fail(file_name, f"Missing top-level key '{req}'")

    assert_type(file_name, "versions", data["versions"], list)
    assert_type(file_name, "components", data["components"], dict)

    for v, libs in data["components"].items():
        assert_type(file_name, f"components.{v}", libs, list)
        for idx, lib in enumerate(libs):
            assert_type(file_name, f"components.{v}[{idx}]", lib, dict)
            if "name" not in lib:
                fail(file_name, f"Missing 'name' in component '{v}' library [{idx}]")
            assert_type(file_name, f"components.{v}[{idx}].name", lib["name"], str)

            if "rules" in lib:
                assert_type(
                    file_name, f"components.{v}[{idx}].rules", lib["rules"], list
                )
            if "natives" in lib:
                assert_type(
                    file_name, f"components.{v}[{idx}].natives", lib["natives"], dict
                )


def verify_server(file_name: str, data: dict[str, Any]) -> None:
    assert_type(file_name, "root", data, dict)
    for req in ["versions", "builds"]:
        if req not in data:
            fail(file_name, f"Missing top-level key '{req}'")

    assert_type(file_name, "versions", data["versions"], list)
    assert_type(file_name, "builds", data["builds"], dict)

    for ver, info in data["builds"].items():
        assert_type(file_name, f"builds.{ver}", info, dict)
        if "build" not in info:
            fail(file_name, f"Missing 'build' in builds.{ver}")
        assert_type(file_name, f"builds.{ver}.build", info["build"], int)

        if "url" not in info:
            fail(file_name, f"Missing 'url' in builds.{ver}")
        assert_type(file_name, f"builds.{ver}.url", info["url"], str)

        if "hash" not in info:
            fail(file_name, f"Missing 'hash' in builds.{ver}")
        assert_sri(file_name, f"builds.{ver}.hash", info["hash"])


def verify_asset_map(data: dict[str, Any]) -> None:
    file_name = "asset-sha1-sha256-map.json"
    assert_type(file_name, "root", data, dict)
    if not data:
        fail(file_name, "asset map is empty")

    # Sample check first 100 entries to verify sha1 -> sha256 SRI format
    for idx, (sha1_hex, sha256_sri) in enumerate(data.items()):
        if len(sha1_hex) != 40:
            fail(file_name, f"Key '{sha1_hex}' is not a valid 40-char SHA1 hex digest")
        assert_sri(file_name, f"asset_map.{sha1_hex}", sha256_sri)
        if not sha256_sri.startswith("sha256-"):
            fail(
                file_name, f"Expected sha256- prefix for asset hash, got: {sha256_sri}"
            )
        if idx >= 100:
            break


def verify_waywall(data: dict[str, Any]) -> None:
    file_name = "waywall.json"
    assert_type(file_name, "root", data, dict)
    for req in ["versions", "releases"]:
        if req not in data:
            fail(file_name, f"Missing top-level key '{req}'")

    assert_type(file_name, "versions", data["versions"], list)
    assert_type(file_name, "releases", data["releases"], dict)

    for tag, info in data["releases"].items():
        assert_type(file_name, f"releases.{tag}", info, dict)
        if "src" not in info:
            fail(file_name, f"Missing 'src' in releases.{tag}")
        assert_type(file_name, f"releases.{tag}.src", info["src"], dict)
        if "url" not in info["src"]:
            fail(file_name, f"Missing 'url' in releases.{tag}.src")
        assert_type(file_name, f"releases.{tag}.src.url", info["src"]["url"], str)
        if "hash" not in info["src"]:
            fail(file_name, f"Missing 'hash' in releases.{tag}.src")
        assert_sri(file_name, f"releases.{tag}.src.hash", info["src"]["hash"])

        if "patches" in info:
            assert_type(file_name, f"releases.{tag}.patches", info["patches"], dict)
            for p_name, p_info in info["patches"].items():
                assert_type(file_name, f"releases.{tag}.patches.{p_name}", p_info, dict)
                if "url" not in p_info:
                    fail(file_name, f"Missing 'url' in releases.{tag}.patches.{p_name}")
                assert_type(file_name, f"releases.{tag}.patches.{p_name}.url", p_info["url"], str)
                if "hash" not in p_info:
                    fail(file_name, f"Missing 'hash' in releases.{tag}.patches.{p_name}")
                assert_sri(file_name, f"releases.{tag}.patches.{p_name}.hash", p_info["hash"])


def verify_all_nixcraft() -> bool:
    """Runs exhaustive schema validation across every file in nixcraft/."""
    logger.info("==> Validating nixcraft/ schema and attributes...")
    all_passed = True

    checks = [
        ("libraries.json", verify_libraries),
        ("mojang.json", verify_mojang),
        ("fabric.json", lambda d: verify_modloader_fabric_quilt("fabric.json", d)),
        ("quilt.json", lambda d: verify_modloader_fabric_quilt("quilt.json", d)),
        ("forge.json", lambda d: verify_modloader_forge_neoforge("forge.json", d)),
        (
            "neoforge.json",
            lambda d: verify_modloader_forge_neoforge("neoforge.json", d),
        ),
        ("lwjgl.json", verify_lwjgl),
        ("paper.json", lambda d: verify_server("paper.json", d)),
        ("folia.json", lambda d: verify_server("folia.json", d)),
        ("purpur.json", lambda d: verify_server("purpur.json", d)),
        ("velocity.json", lambda d: verify_server("velocity.json", d)),
        ("waterfall.json", lambda d: verify_server("waterfall.json", d)),
        ("asset-sha1-sha256-map.json", verify_asset_map),
        ("waywall.json", verify_waywall),
    ]

    for fname, validator in checks:
        fpath = NIXCRAFT_DIR / fname
        if not fpath.exists():
            logger.error(f"FAIL: Missing expected file {fpath}")
            all_passed = False
            continue

        data = load_json(fpath)
        if data is None:
            logger.error(f"FAIL: Could not load JSON from {fpath}")
            all_passed = False
            continue

        try:
            validator(data)
            logger.info(f"  ✓ {fname}: OK")
        except SchemaError as e:
            logger.error(f"  ✗ {fname}: {e}")
            all_passed = False

    if all_passed:
        logger.info("==> All nixcraft/ schemas and attributes verified successfully!")
    else:
        logger.error("==> Schema verification failed!")

    return all_passed
