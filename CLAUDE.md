# AIEOS Adapter — publish.manifest via kustomize + git

Claims: `publish.manifest` at 1.0.0. output_schema: null.
Contract: `aieos-governance-foundation/contracts/publish.manifest.contract.yaml`.

Inputs: manifest_source_path (overlay root), artifact_ref_to_substitute
(OCI digest), target_repo_ref (manifests repo dir), target_path (file path
inside the target repo).

Unit tests mock subprocess; real conformance requires kustomize + git.
