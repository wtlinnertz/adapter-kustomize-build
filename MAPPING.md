# MAPPING — adapter-kustomize-build

## Tool

kustomize + git. Three steps:

1. `kustomize edit set image _ignored_name=<artifact_ref>` in the overlay
   source directory. Kustomize's `edit set image` uses the first image
   declared in kustomization.yaml and overrides its digest; the name-left-
   of-equals is not validated by kustomize. Callers that need name-aware
   substitution should pre-edit kustomization.yaml.
2. `kustomize build <source>` rendering the final manifests to stdout.
3. `git add <target_path>; git commit --allow-empty -m "publish.manifest: <ref>"`
   inside target_repo_ref.

## Evidence

- `manifests-repo-commit-sha:<sha>` — the commit that now reflects the
  rendered manifests. Downstream deploy.environment watches this SHA.
- `manifest-bundle-ref:<target_repo>/<target_path>` — the file that holds
  the rendered bundle.
- `manifest-size:<bytes>` — sanity check on the bundle size.
- `exit-code:0`.

## Exit code

0 on successful render + commit; 2 missing source/target dir; 127 kustomize
missing; 3 kustomize zero-exit with empty output; pass-through otherwise.
