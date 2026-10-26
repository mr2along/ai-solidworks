import json
import logging
import os
import shutil
import subprocess
import tempfile
import zipfile
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from .export_pdf import export_dimension_pdf
from .schemas import GenerateRequest, PlanRequest, JobResponse
from .planner import plan_from_description

app = FastAPI(title="AI CAD Agent", version="0.3.0")
ROOT = Path(__file__).resolve().parents[1]
FREECAD_SCRIPT = ROOT / "cad" / "freecad_generate.py"
FREECAD_SMOKE_SCRIPT = ROOT / "cad" / "freecad_smoke.py"
_GENERATION_LOCK = threading.BoundedSemaphore(1)
logger = logging.getLogger(__name__)


def _freecad_command():
    configured = os.getenv("FREECAD_CMD", "FreeCADCmd")
    candidates = [
        configured, "FreeCADCmd", "freecadcmd", "freecadcmd-python3",
        "FreeCAD", "freecad",
        "/usr/lib/freecad/bin/FreeCADCmd",
        "/usr/lib/freecad/bin/freecadcmd",
        "/usr/lib/freecad/bin/freecadcmd-python3",
        "/usr/lib/freecad/bin/FreeCAD",
    ]
    for candidate in candidates:
        resolved = shutil.which(candidate) if not candidate.startswith("/") else candidate
        if resolved and os.path.isfile(resolved) and os.access(resolved, os.X_OK):
            return resolved
    raise FileNotFoundError(
        "Không tìm thấy FreeCAD headless. Kiểm tra gói freecad-python3 trong Docker image."
    )


def _freecad_argv(command, script):
    is_gui_binary = Path(command).name.lower() in {"freecad", "freecad.exe"}
    return [command] + (["--console"] if is_gui_binary else []) + [str(script)]


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-cad-generator"}


@app.get("/api/health/cad")
def cad_health():
    try:
        command = _freecad_command()
    except FileNotFoundError as exc:
        logger.error("FreeCAD executable is unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="FreeCAD backend is unavailable.") from exc

    try:
        result = subprocess.run(
            _freecad_argv(command, FREECAD_SMOKE_SCRIPT),
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.error("FreeCAD runtime probe timed out.")
        raise HTTPException(status_code=503, detail="FreeCAD runtime check timed out.") from exc
    except OSError as exc:
        logger.exception("FreeCAD runtime probe could not start.")
        raise HTTPException(status_code=503, detail="FreeCAD runtime is unavailable.") from exc

    marker = next(
        (line for line in result.stdout.splitlines() if line.startswith("FREECAD_RUNTIME_OK ")),
        None,
    )
    if result.returncode != 0 or marker is None:
        diagnostic = (result.stderr or result.stdout or "No diagnostic output")[-1800:]
        logger.error("FreeCAD runtime probe failed (exit %s): %s", result.returncode, diagnostic)
        raise HTTPException(status_code=503, detail="FreeCAD runtime dependencies are unavailable.")

    return {"status": "available", "backend": "freecad", "version": marker.removeprefix("FREECAD_RUNTIME_OK ")}


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
def generate_cad(request: GenerateRequest):
    # FastAPI validates the nested plan and its geometric constraints again at
    # this boundary; free-form descriptions cannot start CAD generation.
    plan = request.plan

    if not _GENERATION_LOCK.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="Đang xử lý một job CAD khác. Vui lòng thử lại sau.")

    work_dir = None
    correlation_id = uuid.uuid4().hex[:12]
    try:
        try:
            command = _freecad_command()
        except FileNotFoundError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        work_dir = tempfile.mkdtemp(prefix="ai-cad-")
        output_dir = os.path.join(work_dir, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        config_path = os.path.join(work_dir, "plan.json")
        archive_path = os.path.join(work_dir, f"{plan.part_name}-cad-files.zip")
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(plan.model_dump(mode="json"), handle, ensure_ascii=False)

        env = os.environ.copy()
        env["CAD_JOB_CONFIG"] = config_path
        env["CAD_OUTPUT_DIR"] = output_dir
        argv = _freecad_argv(command, FREECAD_SCRIPT)

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
        except subprocess.TimeoutExpired as exc:
            logger.error("FreeCAD generation timed out (correlation_id=%s).", correlation_id)
            raise HTTPException(
                status_code=504,
                detail=f"FreeCAD vượt quá thời gian xử lý cho phép. Mã tham chiếu: {correlation_id}.",
                headers={"X-Correlation-ID": correlation_id},
            ) from exc

        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout or "Không có log từ FreeCAD")[-1800:]
            logger.error(
                "FreeCAD generation failed (correlation_id=%s, exit=%s): %s",
                correlation_id,
                completed.returncode,
                diagnostic,
            )
            raise HTTPException(
                status_code=500,
                detail=f"FreeCAD không thể tạo mô hình. Mã tham chiếu: {correlation_id}.",
                headers={"X-Correlation-ID": correlation_id},
            )

        expected = [
            os.path.join(output_dir, f"{plan.part_name}.FCStd"),
            os.path.join(output_dir, f"{plan.part_name}.step"),
            os.path.join(output_dir, f"{plan.part_name}.stl"),
        ]
        missing = [path for path in expected if not os.path.isfile(path) or os.path.getsize(path) == 0]
        if missing:
            diagnostic = (completed.stderr or completed.stdout or "")[-1200:]
            logger.error(
                "FreeCAD omitted required artifacts (correlation_id=%s, missing=%s): %s",
                correlation_id,
                [os.path.basename(path) for path in missing],
                diagnostic,
            )
            raise HTTPException(
                status_code=500,
                detail=f"FreeCAD chưa tạo đủ file đầu ra. Mã tham chiếu: {correlation_id}.",
                headers={"X-Correlation-ID": correlation_id},
            )

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
    except HTTPException:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except Exception:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        logger.exception("Unhandled CAD generation failure (correlation_id=%s).", correlation_id)
        raise HTTPException(
            status_code=500,
            detail=f"Không thể hoàn tất tạo file CAD. Mã tham chiếu: {correlation_id}.",
            headers={"X-Correlation-ID": correlation_id},
        ) from None
    finally:
        _GENERATION_LOCK.release()


frontend_dist = ROOT / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
