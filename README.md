# AI SolidWorks — MVP

Text-to-CAD prototype for SOLIDWORKS on Windows.

## Architecture
- `frontend/`: React + TypeScript web UI for submitting a description and previewing the validated CAD plan.
- `backend/`: FastAPI job API, CAD-plan schema, validation and deterministic demo planner.
- `windows_agent/`: Windows-only SOLIDWORKS COM worker using `pywin32`.
- `tests/`: portable tests for CAD plan validation.

The backend does **not** control SOLIDWORKS directly. The Windows Agent runs on the logged-in Windows desktop where SOLIDWORKS is installed.

## MVP scope
Initial supported operations: rectangular base plate and simple through-holes. The first version intentionally avoids arbitrary AI-generated code. Planner output is validated JSON interpreted by fixed, reviewed CAD functions.

## Quick start — backend
Python 3.10+ recommended.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000/docs.

## Quick start — web UI
In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite. The Vite development server proxies `/api` and `/health` to the backend on port 8000.

Set `AI_API_KEY` only if you later implement an LLM provider adapter. The current planner is deterministic/demo and does not require an API key.

## Windows Agent prerequisites
- Windows desktop session with SOLIDWORKS installed and licensed.
- Python version/bitness compatible with the installed SOLIDWORKS COM environment.
- Install `pywin32` and test COM access locally.
- Configure a trusted backend URL and agent token before enabling remote jobs.

**Safety:** Do not expose the Agent listener to the public internet. Use outbound authenticated connections, allowlisted output directories, one CAD job at a time, and human approval before executing generated plans. Do not store API keys in source control.

## Example request
```json
{
  "description": "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
  "part_name": "mounting_plate"
}
```

The demo planner supports this explicit plate pattern. Arbitrary Vietnamese descriptions need an LLM adapter and follow-up questions when dimensions are missing.

## Status
Scaffold only. CAD automation requires validation against the exact installed SOLIDWORKS version and a local Windows test run.
