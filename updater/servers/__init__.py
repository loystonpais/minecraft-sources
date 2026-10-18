from updater.servers.papermc import update_papermc_project, PAPERMC_PROJECTS
from updater.servers.purpur import update_purpur

AVAILABLE_SERVERS = list(PAPERMC_PROJECTS.keys()) + ["purpur"]


def update_server(name: str) -> None:
    """Updates a server software project (raw project manifest + normalized latest builds)."""
    target = name.lower()
    if target == "purpur":
        update_purpur()
    elif target in PAPERMC_PROJECTS:
        update_papermc_project(target)
    else:
        raise ValueError(f"Unknown server software '{target}'. Available: {AVAILABLE_SERVERS}")
