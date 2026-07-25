"""ResponseModel / PageModel unit tests."""

from __future__ import annotations

from app.schemas.response import PageModel, ResponseModel, error_response, success_response


def test_success_response_shape():
    body = success_response({"a": 1}, request_id="rid-1")
    dumped = body.model_dump()
    assert dumped["code"] == 0
    assert dumped["message"] == "ok"
    assert dumped["data"] == {"a": 1}
    assert dumped["request_id"] == "rid-1"
    assert "T" in dumped["timestamp"]


def test_error_response_shape():
    body = error_response(code=1001, message="parameter error", request_id="rid-2")
    assert body.code == 1001
    assert body.data is None


def test_page_model():
    page = PageModel(items=[1, 2], total=2, page=1, page_size=10)
    assert page.total == 2
    assert len(page.items) == 2


def test_response_model_generic_roundtrip():
    model = ResponseModel[dict](code=0, message="ok", data={"x": 1}, request_id="r")
    assert model.data["x"] == 1
