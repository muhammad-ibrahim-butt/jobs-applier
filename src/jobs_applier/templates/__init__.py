"""Resolve bundled template files for `jobs-applier init`."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

# Map destination basename -> packaged template filename
TEMPLATE_MAP: dict[str, str] = {
    ".env": "env.example",
    "config.yaml": "config.example.yaml",
    "profile.yaml": "profile.example.yaml",
}


def find_template(destination_name: str) -> Path | None:
    """Locate a template for a destination config file."""
    packaged_name = TEMPLATE_MAP.get(destination_name, destination_name)

    try:
        pkg = resources.files("jobs_applier.templates")
        candidate = pkg.joinpath(packaged_name)
        if candidate.is_file():
            with resources.as_file(candidate) as path:
                return Path(path)
    except (TypeError, FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass

    here = Path(__file__).resolve().parent
    packaged_path = here / packaged_name
    if packaged_path.is_file():
        return packaged_path

    # templates/ -> jobs_applier/ -> src/ -> repo root
    repo_root = here.parents[3]
    for relative in (
        Path(destination_name) if destination_name.startswith(".") else None,
        Path("config.example.yaml") if destination_name == "config.yaml" else None,
        Path("profile.example.yaml") if destination_name == "profile.yaml" else None,
        Path(".env.example") if destination_name == ".env" else None,
    ):
        if relative is None:
            continue
        path = repo_root / relative
        if path.is_file():
            return path

    cwd_candidates = {
        ".env": [".env.example"],
        "config.yaml": ["config.example.yaml"],
        "profile.yaml": ["profile.example.yaml"],
    }.get(destination_name, [])
    for name in cwd_candidates:
        path = Path.cwd() / name
        if path.is_file():
            return path

    return None
