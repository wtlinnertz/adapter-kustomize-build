# adapter-kustomize-build

AIEOS adapter: `publish.manifest` via kustomize + git. Renders a kustomize
overlay with a substituted image digest, writes the bundle to a path in
the target manifests repository, and commits. Evidence: the resulting
commit SHA plus the manifest bundle reference.

No findings schema — publish.manifest's output_schema is null per the contract.

MIT.
