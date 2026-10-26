import subprocess

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend import main
from backend.schemas import GenerateRequest


def test_cad_health_checks_required_freecad_imports(monkeypatch):
    monkeypatch.setattr(main, "_freecad_command", lambda: "/usr/bin/freecadcmd")
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, "FREECAD_RUNTIME_OK FreeCAD 0.20.2\n", ""
        ),
    )

    assert main.cad_health() == {
        "status": "available",
        "backend": "freecad",
        "version": "FreeCAD 0.20.2",
    }


def test_cad_health_does_not_expose_runtime_traceback(monkeypatch):
    monkeypatch.setattr(main, "_freecad_command", lambda: "/usr/bin/freecadcmd")
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 1, "", "ModuleNotFoundError: No module named 'math'\n/private/path"
        ),
    )

    with pytest.raises(HTTPException) as error:
        main.cad_health()

    assert error.value.status_code == 503
    assert error.value.detail == "FreeCAD runtime dependencies are unavailable."
    assert "ModuleNotFoundError" not in error.value.detail
    assert "/private/path" not in error.value.detail


def test_generation_error_does_not_return_freecad_traceback(monkeypatch):
    monkeypatch.setattr(main, "_freecad_command", lambda: "/usr/bin/freecadcmd")
    monkeypatch.setattr(
        main.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            0,
            "Traceback: ModuleNotFoundError: No module named 'math'\n/private/path",
            "",
        ),
    )

    plan = main.plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
        "failed_plate",
    )
    with pytest.raises(HTTPException) as error:
        main.generate_cad(GenerateRequest(plan=plan))

    assert error.value.status_code == 500
    assert "ModuleNotFoundError" not in error.value.detail
    assert "/private/path" not in error.value.detail
    assert error.value.headers["X-Correlation-ID"] in error.value.detail


def test_generate_uses_and_revalidates_the_reviewed_plan(monkeypatch):
    import json

    plan = main.plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
        "reviewed_plate",
    )
    monkeypatch.setattr(main, "plan_from_description", lambda *args: pytest.fail("planner must not rerun"))
    monkeypatch.setattr(main, "_freecad_command", lambda: "/usr/bin/freecadcmd")

    def failed_generation(argv, *, env, **kwargs):
        with open(env["CAD_JOB_CONFIG"], encoding="utf-8") as config:
            serialized = json.load(config)
        assert serialized["part_name"] == "reviewed_plate"
        assert serialized["features"][0]["length"] == 100
        return subprocess.CompletedProcess(argv, 1, "FreeCAD failed", "")

    monkeypatch.setattr(main.subprocess, "run", failed_generation)
    with pytest.raises(HTTPException) as error:
        main.generate_cad(GenerateRequest(plan=plan))

    assert error.value.status_code == 500


def test_generate_request_revalidates_a_mutated_plan_instance():
    plan = main.plan_from_description(
        "Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm"
    )
    plan.features[0].length = -1

    with pytest.raises(ValidationError):
        GenerateRequest(plan=plan)
