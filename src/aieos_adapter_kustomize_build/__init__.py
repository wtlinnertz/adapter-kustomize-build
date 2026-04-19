"""AIEOS adapter: publish.manifest via kustomize + git.

Renders a Kustomize overlay into a manifest bundle, writes it into a clone
of the target manifests repository, and commits. Evidence is the resulting
commit SHA plus the bundle size.

No findings schema; publish.manifest's output_schema is null per the contract.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__version__ = "1.0.0"

_SHA_PATTERN = re.compile(r"\b[0-9a-f]{40}\b")


@dataclass
class AdapterResult:
    findings: dict[str, Any] | None
    evidence: list[str]
    exit_code: int


class KustomizeBuildAdapter:
    def __init__(
        self,
        kustomize_binary: str = "kustomize",
        git_binary: str = "git",
    ) -> None:
        self._kustomize = kustomize_binary
        self._git = git_binary

    def execute(self, inputs: dict[str, Any]) -> AdapterResult:
        source_path = Path(inputs["manifest_source_path"]).resolve()
        artifact_ref = inputs["artifact_ref_to_substitute"]
        target_repo = Path(inputs["target_repo_ref"]).resolve()
        target_path = inputs["target_path"]

        if not source_path.is_dir():
            return AdapterResult(findings=None, evidence=["exit-code:2"], exit_code=2)
        if not target_repo.is_dir():
            return AdapterResult(findings=None, evidence=["exit-code:2"], exit_code=2)

        # Step 1: update image in the kustomization to the provided digest.
        image_ref_arg = f"_ignored_name={artifact_ref}"
        edit_cmd = [self._kustomize, "edit", "set", "image", image_ref_arg]
        try:
            edit_proc = subprocess.run(
                edit_cmd,
                cwd=source_path,
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return AdapterResult(
                findings=None,
                evidence=["exit-code:127", "stderr:kustomize not on $PATH"],
                exit_code=127,
            )
        if edit_proc.returncode != 0:
            return AdapterResult(
                findings=None,
                evidence=[
                    f"exit-code:{edit_proc.returncode}",
                    "stderr:" + (edit_proc.stderr[:500] or ""),
                ],
                exit_code=edit_proc.returncode,
            )

        # Step 2: render the manifests.
        build_proc = subprocess.run(
            [self._kustomize, "build", str(source_path)],
            check=False,
            capture_output=True,
            text=True,
        )
        if build_proc.returncode != 0 or not build_proc.stdout.strip():
            return AdapterResult(
                findings=None,
                evidence=[
                    f"exit-code:{build_proc.returncode}",
                    "stderr:" + (build_proc.stderr[:500] or ""),
                ],
                exit_code=build_proc.returncode if build_proc.returncode != 0 else 3,
            )
        manifests = build_proc.stdout

        # Step 3: write into target_repo/<target_path> and commit.
        target = target_repo / target_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(manifests)

        commit_proc = _git_commit(
            self._git,
            repo=target_repo,
            path=str(target.relative_to(target_repo)),
            message=f"publish.manifest: {artifact_ref}",
        )
        if commit_proc.returncode != 0:
            return AdapterResult(
                findings=None,
                evidence=[
                    f"exit-code:{commit_proc.returncode}",
                    "stderr:" + (commit_proc.stderr[:500] or ""),
                ],
                exit_code=commit_proc.returncode,
            )

        head = _git_head_sha(self._git, target_repo)
        return AdapterResult(
            findings=None,
            evidence=[
                f"manifests-repo-commit-sha:{head}",
                f"manifest-bundle-ref:{target}",
                f"manifest-size:{len(manifests)}",
                "exit-code:0",
            ],
            exit_code=0,
        )


def _git_commit(git: str, repo: Path, path: str, message: str) -> subprocess.CompletedProcess:
    # Stage + commit in one shot; tolerate "nothing to commit" gracefully.
    subprocess.run([git, "add", path], cwd=repo, check=False, capture_output=True, text=True)
    return subprocess.run(
        [git, "commit", "-m", message, "--allow-empty"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )


def _git_head_sha(git: str, repo: Path) -> str:
    proc = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    match = _SHA_PATTERN.search(proc.stdout or "")
    return match.group(0) if match else ""
