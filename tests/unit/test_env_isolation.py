"""Tests that importing the library never mutates the host process environment.

The library is consumed as a dependency by applications that manage their own
environment layering (exported vars, systemd ``EnvironmentFile``, layered
``.env`` files read by their own settings loader). Importing
``wikidata_collector`` must therefore be free of side effects on
``os.environ`` — a ``.env`` file that happens to sit above the installed
package must never be promoted into real environment variables.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from wikidata_collector.config import load_env_file

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "wikidata_collector"
SENTINEL_KEY = "WIKIDATA_COLLECTOR_ENV_SENTINEL"


@pytest.fixture
def preserved_environ():
    """Snapshot ``os.environ`` and restore it after the test."""
    snapshot = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(snapshot)


def _make_importable_tree(tmp_path: Path) -> Path:
    """Lay out a package tree nested below a directory holding a ``.env``.

    Mirrors a real installation: the package lives inside a site-packages-like
    directory below the consuming application's project root, so a naive
    upward ``.env`` search from the package file reaches the application's
    ``.env``.

    Args:
        tmp_path: Temporary directory acting as the application project root.

    Returns:
        The directory to put on ``PYTHONPATH`` so the package is importable.
    """
    site_packages = tmp_path / "site-packages"
    site_packages.mkdir()
    (site_packages / "wikidata_collector").symlink_to(PACKAGE_DIR, target_is_directory=True)
    (tmp_path / ".env").write_text(f"{SENTINEL_KEY}=leaked\n", encoding="utf-8")
    return site_packages


def _run_import_probe(tmp_path: Path, script: str) -> str:
    """Run ``script`` in a fresh interpreter rooted at ``tmp_path``.

    Args:
        tmp_path: Application project root containing the sentinel ``.env``.
        script: Python source to execute.

    Returns:
        Stripped stdout of the subprocess.
    """
    site_packages = _make_importable_tree(tmp_path)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(site_packages)
    env.pop(SENTINEL_KEY, None)
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


class TestImportSideEffects:
    """Importing the library must leave ``os.environ`` untouched."""

    def test_importing_package_does_not_promote_dotenv_into_environ(self, tmp_path):
        """``import wikidata_collector`` must not leak a nearby ``.env``."""
        script = (
            "import os\n"
            "import wikidata_collector\n"
            "print(wikidata_collector.__file__)\n"
            f"print(os.environ.get('{SENTINEL_KEY}', '<unset>'))\n"
        )
        module_file, sentinel = _run_import_probe(tmp_path, script).splitlines()
        assert str(tmp_path) in module_file, "probe imported the installed copy, not the tree"
        assert sentinel == "<unset>"

    def test_importing_config_module_does_not_promote_dotenv_into_environ(self, tmp_path):
        """``import wikidata_collector.config`` must not leak a nearby ``.env``."""
        script = (
            "import os\n"
            "import wikidata_collector.config as config\n"
            "print(config.__file__)\n"
            f"print(os.environ.get('{SENTINEL_KEY}', '<unset>'))\n"
        )
        module_file, sentinel = _run_import_probe(tmp_path, script).splitlines()
        assert str(tmp_path) in module_file, "probe imported the installed copy, not the tree"
        assert sentinel == "<unset>"

    def test_building_config_does_not_promote_dotenv_into_environ(self, tmp_path):
        """Instantiating ``WikidataCollectorConfig`` must not leak a nearby ``.env``."""
        script = (
            "import os\n"
            "from wikidata_collector.config import WikidataCollectorConfig\n"
            "WikidataCollectorConfig()\n"
            f"print(os.environ.get('{SENTINEL_KEY}', '<unset>'))\n"
        )
        assert _run_import_probe(tmp_path, script) == "<unset>"

    def test_real_environment_variables_are_still_honoured(self, tmp_path):
        """Exported process env vars remain the configuration channel."""
        site_packages = _make_importable_tree(tmp_path)
        env = dict(os.environ)
        env["PYTHONPATH"] = str(site_packages)
        env["MAX_RETRIES"] = "7"
        env["CONTACT_EMAIL"] = "exported@example.com"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from wikidata_collector.config import WikidataCollectorConfig\n"
                "c = WikidataCollectorConfig()\n"
                "print(c.max_retries, c.contact_email)\n",
            ],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "7 exported@example.com"


class TestLoadEnvFile:
    """The opt-in ``load_env_file`` helper is the only way to read a ``.env``."""

    def test_loads_explicit_path(self, tmp_path, preserved_environ):
        """An explicit path is read into ``os.environ``."""
        env_file = tmp_path / "custom.env"
        env_file.write_text(f"{SENTINEL_KEY}=explicit\n", encoding="utf-8")
        os.environ.pop(SENTINEL_KEY, None)

        assert load_env_file(str(env_file)) is True
        assert os.environ[SENTINEL_KEY] == "explicit"

    def test_discovers_dotenv_from_working_directory(
        self, tmp_path, monkeypatch, preserved_environ
    ):
        """With no path, the nearest ``.env`` above the CWD is used."""
        (tmp_path / ".env").write_text(f"{SENTINEL_KEY}=discovered\n", encoding="utf-8")
        nested = tmp_path / "nested"
        nested.mkdir()
        monkeypatch.chdir(nested)
        os.environ.pop(SENTINEL_KEY, None)

        assert load_env_file() is True
        assert os.environ[SENTINEL_KEY] == "discovered"

    def test_does_not_override_existing_process_variables_by_default(
        self, tmp_path, preserved_environ
    ):
        """Real environment variables outrank ``.env`` values by default."""
        env_file = tmp_path / "custom.env"
        env_file.write_text(f"{SENTINEL_KEY}=from-file\n", encoding="utf-8")
        os.environ[SENTINEL_KEY] = "from-process"

        load_env_file(str(env_file))

        assert os.environ[SENTINEL_KEY] == "from-process"

    def test_override_flag_replaces_existing_process_variables(self, tmp_path, preserved_environ):
        """``override=True`` lets the file win, for callers that want it."""
        env_file = tmp_path / "custom.env"
        env_file.write_text(f"{SENTINEL_KEY}=from-file\n", encoding="utf-8")
        os.environ[SENTINEL_KEY] = "from-process"

        load_env_file(str(env_file), override=True)

        assert os.environ[SENTINEL_KEY] == "from-file"

    def test_returns_false_when_no_dotenv_is_found(self, tmp_path, monkeypatch, preserved_environ):
        """A missing ``.env`` is reported, not raised."""
        empty = tmp_path / "empty"
        empty.mkdir()
        monkeypatch.chdir(empty)
        monkeypatch.setattr("wikidata_collector.config.find_dotenv", lambda **_: "")

        assert load_env_file() is False
