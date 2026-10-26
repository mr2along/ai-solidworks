# Windows CAD Agent

Windows-only component. Run it interactively under the logged-in desktop user that owns the SOLIDWORKS session.

## Current status
This folder documents the integration boundary. COM execution is not enabled until the SOLIDWORKS version, template path, and API behavior are tested on the target workstation.

## Local prerequisites
```powershell
py -m pip install pywin32
```

Start with a local smoke test using SOLIDWORKS API examples from the installed version. Do not accept arbitrary Python/VBA from the AI. The future worker must interpret only validated CADPlan operations, serialize jobs, constrain output paths, and return explicit feature/rebuild/save errors.

Never expose an unauthenticated local HTTP listener to the network.
