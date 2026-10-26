from fastapi import FastAPI, HTTPException
from .schemas import PlanRequest, JobResponse
from .planner import plan_from_description

app = FastAPI(title="AI SolidWorks MVP", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-solidworks-backend"}


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
        message="Kế hoạch đã được kiểm tra. Chưa gửi lệnh đến SOLIDWORKS.",
    )
