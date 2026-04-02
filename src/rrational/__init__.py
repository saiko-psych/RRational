"""Top-level package for RRational HRV analysis toolkit."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rrational")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"


def get_build_info() -> dict[str, str]:
    """Get build/debug information for diagnostics."""
    import platform
    import sys

    info = {
        "version": __version__,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.system(),
        "platform_version": platform.version(),
    }

    # Try to get git commit hash
    try:
        import subprocess
        from pathlib import Path

        repo_root = Path(__file__).parent.parent.parent
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root, capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0:
            info["git_commit"] = result.stdout.strip()
        result2 = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            cwd=repo_root, capture_output=True, text=True, timeout=2,
        )
        if result2.returncode == 0:
            info["git_date"] = result2.stdout.strip()[:10]
    except Exception:
        pass

    return info


__all__ = ["__version__", "get_build_info"]
