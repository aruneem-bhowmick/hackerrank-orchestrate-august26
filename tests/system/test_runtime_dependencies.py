"""Regression checks for packages imported by the command-line entrypoint."""


def test_runtime_requirements_include_media_client_sdks(repo_root):
    """A clean install declares every third-party SDK imported by media ingestion."""
    requirements = (repo_root / "requirements.txt").read_text(encoding="utf-8").splitlines()
    package_names = {line.split(">=", maxsplit=1)[0].strip() for line in requirements if line.strip()}

    assert {"anthropic", "openai"} <= package_names
