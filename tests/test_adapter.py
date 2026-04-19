"""Unit tests for adapter-kustomize-build."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from aieos_adapter_kustomize_build import KustomizeBuildAdapter


class _Proc:
    def __init__(self, rc: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = rc
        self.stdout = stdout
        self.stderr = stderr


def _fake_subprocess(commands_to_outputs):
    """Return a side_effect that matches the first word of cmd to a canned output."""

    def side(cmd, **kw):
        key = cmd[0] + " " + cmd[1] if len(cmd) > 1 else cmd[0]
        for prefix, out in commands_to_outputs.items():
            if key.startswith(prefix):
                return out
        return _Proc(0, "", "")

    return side


def test_missing_source_path_returns_error(tmp_path: Path):
    result = KustomizeBuildAdapter().execute(
        {
            "manifest_source_path": str(tmp_path / "nope"),
            "artifact_ref_to_substitute": "sha256:x",
            "target_repo_ref": str(tmp_path),
            "target_path": "app.yaml",
        }
    )
    assert result.exit_code == 2


def test_missing_target_repo_returns_error(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    result = KustomizeBuildAdapter().execute(
        {
            "manifest_source_path": str(source),
            "artifact_ref_to_substitute": "sha256:x",
            "target_repo_ref": str(tmp_path / "no-repo"),
            "target_path": "app.yaml",
        }
    )
    assert result.exit_code == 2


def test_kustomize_not_installed(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = KustomizeBuildAdapter().execute(
            {
                "manifest_source_path": str(source),
                "artifact_ref_to_substitute": "sha256:x",
                "target_repo_ref": str(repo),
                "target_path": "app.yaml",
            }
        )
    assert result.exit_code == 127


def test_happy_path_emits_expected_evidence(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    calls: list[list[str]] = []

    def _run(cmd, **kw):
        calls.append(list(cmd))
        if cmd[:2] == ["kustomize", "edit"]:
            return _Proc(0)
        if cmd[:2] == ["kustomize", "build"]:
            return _Proc(0, "apiVersion: v1\nkind: ConfigMap\n")
        if cmd[:2] == ["git", "add"]:
            return _Proc(0)
        if cmd[:2] == ["git", "commit"]:
            return _Proc(0)
        if cmd[:2] == ["git", "rev-parse"]:
            return _Proc(0, "0" * 40 + "\n")
        return _Proc(0)

    with patch("subprocess.run", side_effect=_run):
        result = KustomizeBuildAdapter().execute(
            {
                "manifest_source_path": str(source),
                "artifact_ref_to_substitute": "sha256:deadbeef",
                "target_repo_ref": str(repo),
                "target_path": "envs/dev/app.yaml",
            }
        )

    assert result.exit_code == 0
    assert any("manifests-repo-commit-sha:" in e for e in result.evidence)
    assert any("manifest-bundle-ref:" in e for e in result.evidence)
    assert any("manifest-size:" in e for e in result.evidence)
    # Written file exists
    assert (repo / "envs/dev/app.yaml").is_file()


def test_kustomize_edit_failure_propagates(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    def _run(cmd, **kw):
        if cmd[:2] == ["kustomize", "edit"]:
            return _Proc(1, "", "edit failed")
        return _Proc(0)

    with patch("subprocess.run", side_effect=_run):
        result = KustomizeBuildAdapter().execute(
            {
                "manifest_source_path": str(source),
                "artifact_ref_to_substitute": "sha256:x",
                "target_repo_ref": str(repo),
                "target_path": "app.yaml",
            }
        )
    assert result.exit_code == 1
    assert any("edit failed" in e for e in result.evidence)


def test_kustomize_build_empty_output_fails(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()

    def _run(cmd, **kw):
        if cmd[:2] == ["kustomize", "edit"]:
            return _Proc(0)
        if cmd[:2] == ["kustomize", "build"]:
            return _Proc(0, "")
        return _Proc(0)

    with patch("subprocess.run", side_effect=_run):
        result = KustomizeBuildAdapter().execute(
            {
                "manifest_source_path": str(source),
                "artifact_ref_to_substitute": "sha256:x",
                "target_repo_ref": str(repo),
                "target_path": "app.yaml",
            }
        )
    assert result.exit_code == 3
