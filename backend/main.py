import json
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from .export_pdf import export_dimension_pdf
from .schemas import PlanRequest, JobResponse
from .planner import plan_from_description

app = FastAPI(title="AI CAD Generator", version="0.2.0")
ROOT = Path(__file__).resolve().parents[1]
FREECAD_SCRIPT = ROOT / "cad" / "freecad_generate.py"


def _freecad_command():
    configured = os.getenv("FREECAD_CMD", "FreeCADCmd")
    candidates = [configured, "FreeCADCmd", "freecadcmd", "FreeCAD", "freecad",
                  "/usr/lib/freecad/bin/FreeCADCmd",
                  "/usr/lib/freecad/bin/freecadcmd",
                  "/usr/lib/freecad/bin/FreeCAD"]
    for candidate in candidates:
        resolved = shutil.which(candidate) if not candidate.startswith("/") else candidate
        if resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK):
            return resolved
    raise FileNotFoundError(
        "Không tìm thấy FreeCAD headless. Kiểm tra gói freecad trong Docker image."
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-cad-generator"}


@app.get("/api/health/cad")
def cad_health():
    try:
        command = _freecad_command()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "available", "freecad_command": command}


@app.post("/api/plan", response_model=JobResponse)
def create_plan(request: PlanRequest):
    try:
        plan = plan_from_description(request.description, request.part_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JobResponse(
        job_id="plan-preview",
        status="plan_ready",
        plan=plan,
        message="Kế hoạch đã được kiểm tra. Nhấn Tạo file CAD để dựng mô hình bằng FreeCAD.",
    )


@app.post("/api/generate")
def generate_cad(request: PlanRequest):
    try:
        plan = plan_from_description(request.description, request.part_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        command = _freecad_command()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    work_dir = tempfile.mkdtemp(prefix="ai-cad-")
    output_dir = os.path.join(work_dir, "outputs")
    os.makedirs(output_dir, exist_ok=True)
    config_path = os.path.join(work_dir, "plan.json")
    archive_path = os.path.join(work_dir, f'{plan.part_name}-cad-files.zip')
    with open(config_path, "w", encoding="utf-8") as handle:
        json.dump(plan.model_dump(mode="json"), handle, ensure_ascii=False)

    env = os.environ.copy()
    env["CAD_JOB_CONFIG"] = config_path
    env["CAD_OUTPUT_DIR"] = output_dir
    is_gui_binary = Path(command).name.lower() in {"freecad", "freecad.exe"}
    argv = [command] + (["--console"] if is_gui_binary else []) + [str(FREECAD_SCRIPT)]

    try:
        completed = subprocess.run(
            argv,
            cwd=work_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("CAD_MAX_RUNTIME_SECONDS", "90")),
            check=False,
        )
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout or "Không có log từ FreeCAD")[-1800:]
            raise RuntimeError(f"FreeCAD thất bại (exit {completed.returncode}): {diagnostic}")

        expected = [
            os.path.join(output_dir, f"{plan.part_name}.FCStd"),
            os.path.join(output_dir, f"{plan.part_name}.step"),
            os.path.join(output_dir, f"{plan.part_name}.stl"),
        ]
        missing = [path for path in expected if not os.path.isfile(path) or os.path.getsize(path) == 0]
        if missing:
            diagnostic = (completed.stderr or completed.stdout or "")[-1200:]
            raise RuntimeError("FreeCAD chưa tạo đủ file đầu ra: " + ", ".join(os.path.basename(p) for p in missing) + ". " + diagnostic)

        export_dimension_pdf(
            plan.model_dump(mode="json"),
            os.path.join(output_dir, f"{plan.part_name}.pdf"),
        )
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for filename in (
                f"{plan.part_name}.FCStd",
                f"{plan.part_name}.step",
                f"{plan.part_name}.stl",
                f"{plan.part_name}.pdf",
            ):
                archive.write(os.path.join(output_dir, filename), arcname=filename)

        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=f"{plan.part_name}-cad-files.zip",
            background=BackgroundTask(shutil.rmtree, work_dir, ignore_errors=True),
        )
    except subprocess.TimeoutExpired as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=504, detail="FreeCAD vượt quá thời gian xử lý cho phép.") from exc
    except Exception as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
