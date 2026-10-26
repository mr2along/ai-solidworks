import subprocess

import pytest
from fastapi import HTTPException

from backend import main


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

    with pytest.raises(HTTPException) as error:
        main.generate_cad(
            main.PlanRequest(
                description="Vẽ tấm dài 100 mm rộng 60 mm dày 5 mm, 4 lỗ Ø6 cách mép 10 mm",
                part_name="failed_plate",
            )
        )

    assert error.value.status_code == 500
    assert "ModuleNotFoundError" not in error.value.detail
    assert "/private/path" not in error.value.detail
    assert error.value.headers["X-Correlation-ID"] in error.value.detail
