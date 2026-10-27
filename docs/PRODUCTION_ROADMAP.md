# Production upgrade roadmap

## Current baseline

The repository already contains a working FreeCAD headless MVP with:
- A two-step plan/approve/generate flow.
- Parametric request validation for rectangular plates, four through-holes, rounded through-slots and blind rectangular pockets.
- FCStd, STEP, STL and preliminary PDF outputs.
- Docker/FreeCAD smoke tests and GitHub Actions.
- A separate assembly drawing PDF workflow on the `feature/assembly-drawing` branch.

This baseline must be preserved. The current FreeCAD executor still generates a single connected solid for the supported plate feature family; it is not yet a general multi-part assembly engine.

## Upgrade sequence

### Phase 1 — Parameter provenance (this branch)
- Add typed parameter metadata for USER_PROVIDED, MEASURED, DERIVED, ESTIMATED and TBD.
- Require sources for user-provided and measured parameters.
- Prevent TBD parameters from carrying fabricated values.
- Keep the new schema isolated until migration tests are ready.

### Phase 2 — Multi-component design schema
- Add a versioned assembly schema without changing CAD Plan 1.0–1.2 semantics.
- Define component instances, placements, local coordinate systems, feature dependencies and material metadata.
- Add migration and compatibility tests.

### Phase 3 — Mechanical CAD templates
- Implement reusable FreeCAD builders for shafts, rollers, structural members, mounting plates, gussets and roll-holder assemblies.
- Verify shape validity, bounding boxes, axis alignment, intended contacts and interference checks.
- Mark unmeasured parameters as ESTIMATED or TBD.

### Phase 4 — Automotive connector templates
- Implement conceptual connector housings, cavity arrays, terminal references, seals and secondary locks as separate components.
- Validate cavity pitch, basic wall thickness, insertion envelope and component interference.
- Do not claim automotive qualification or copy proprietary dimensions without authorized data.

### Phase 5 — API and artifacts
- Return independent status for generation, validation and each requested export.
- Keep artifact paths isolated per job and verify FCStd reopen and STEP re-import where supported.
- Add bounded job execution and clear diagnostics.

### Phase 6 — CI/CD and deployment
- Run unit tests, frontend build, Docker build and real FreeCAD generation smoke tests before publishing.
- Preserve the existing GitHub Actions Trusted Publisher/OIDC setup for the Hugging Face Space.
- Verify a real generation request and artifact retrieval after deployment.

## Acceptance rule

A capability is not complete merely because its schema or builder exists. It must have a working test in the actual FreeCAD runtime, an API-level test where applicable, and accurate reporting of skipped checks.
