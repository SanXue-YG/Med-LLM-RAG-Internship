"""RAG pipeline facade for the FastAPI layer."""

from __future__ import annotations

from typing import Any, Callable, Protocol

import httpx

from app.config import DEFAULT_CONFIG, Stage11Config
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppException
from app.core.logging import get_logger
from app.services.session_store import SessionTurn, format_session_prefix
from app.state import RUNTIME

logger = get_logger("rag_service")


class PipelineLike(Protocol):
    def run(self, query: str, **kwargs: Any) -> dict[str, Any] | Any: ...


PipelineFactory = Callable[[], PipelineLike]


class RagService:
    """Lazy-load ConstrainedGenerationPipeline (or injected mock) and answer queries.

    Session history is NOT passed into upstream ``run`` (08/10 have no such arg).
    MVP: optional short prefix concatenated onto ``query``.
    """

    def __init__(
        self,
        config: Stage11Config | None = None,
        *,
        pipeline: PipelineLike | None = None,
        pipeline_factory: PipelineFactory | None = None,
        inject_history: bool = True,
    ) -> None:
        self.config = config or DEFAULT_CONFIG
        self._pipeline = pipeline
        self._pipeline_factory = pipeline_factory
        self.inject_history = inject_history
        if pipeline is not None:
            self._mark_ready()

    @property
    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def ensure_pipeline(self) -> PipelineLike:
        """Lazy singleton load; updates ``RUNTIME`` for ``/ready``."""
        if self._pipeline is not None:
            return self._pipeline
        try:
            if self._pipeline_factory is not None:
                self._pipeline = self._pipeline_factory()
            else:
                self._pipeline = self._default_factory()
            self._mark_ready()
            logger.info(
                "pipeline_loaded backend=%s mode=%s",
                self.config.pipeline_backend,
                self.config.retrieval_mode,
            )
            return self._pipeline
        except AppException:
            raise
        except Exception as exc:  # noqa: BLE001
            RUNTIME.pipeline_loaded = False
            RUNTIME.last_error = f"{type(exc).__name__}: {exc}"
            logger.exception("pipeline_load_failed")
            raise AppException(
                ErrorCode.PIPELINE_FAILED,
                message="failed to load RAG pipeline",
                detail=RUNTIME.last_error,
            ) from exc

    def answer(
        self,
        query: str,
        *,
        top_k: int | None = None,
        session_history: list[SessionTurn] | None = None,
    ) -> dict[str, Any]:
        """Run one QA turn.

        Returns a normalized dict with at least ``answer`` / ``sources``, plus
        upstream fields when available (``constraint_checks``, metrics, …).
        Also includes ``effective_query`` and ``top_k_applied`` for observability.
        """
        q = (query or "").strip()
        if not q:
            raise AppException(ErrorCode.PARAM_ERROR, detail="query is empty")

        k = self.config.top_k_default if top_k is None else int(top_k)
        if k < self.config.top_k_min or k > self.config.top_k_max:
            raise AppException(
                ErrorCode.PARAM_ERROR,
                detail={
                    "top_k": k,
                    "allowed": [self.config.top_k_min, self.config.top_k_max],
                },
            )

        prefix = ""
        if self.inject_history and session_history:
            prefix = format_session_prefix(session_history)
        effective_query = f"{prefix}{q}" if prefix else q

        pipeline = self.ensure_pipeline()
        restore = self._apply_top_k(pipeline, k)
        try:
            raw = pipeline.run(effective_query)
            result = self._normalize_result(raw)
        except AppException:
            raise
        except (httpx.HTTPError, httpx.TimeoutException, TimeoutError, ConnectionError) as exc:
            RUNTIME.last_error = f"{type(exc).__name__}: {exc}"
            raise AppException(
                ErrorCode.MODEL_CALL_FAILED,
                message="model call failed",
                detail=RUNTIME.last_error,
            ) from exc
        except Exception as exc:  # noqa: BLE001
            RUNTIME.last_error = f"{type(exc).__name__}: {exc}"
            raise AppException(
                ErrorCode.PIPELINE_FAILED,
                message="pipeline failed",
                detail=RUNTIME.last_error,
            ) from exc
        finally:
            self._restore_top_k(pipeline, restore)

        sources = list(result.get("sources") or [])
        top_k_mode = restore.get("mode", "none")
        if top_k_mode == "truncate_sources" and len(sources) > k:
            sources = sources[:k]
            result["sources"] = sources
            metrics = dict(result.get("generation_metrics") or {})
            metrics["top_k_truncated"] = True
            result["generation_metrics"] = metrics

        result["effective_query"] = effective_query
        result["top_k_applied"] = k
        result["top_k_mode"] = top_k_mode
        result["query"] = q
        return result

    def _default_factory(self) -> PipelineLike:
        backend = self.config.pipeline_backend
        mode = self.config.retrieval_mode
        if backend == "constrained10":
            from constrained_pipeline import ConstrainedGenerationPipeline  # type: ignore

            return ConstrainedGenerationPipeline.from_mode(
                mode,
                skip_evidence_eval=True,
                skip_critical_review=True,
            )
        if backend == "medical08":
            raise AppException(
                ErrorCode.PIPELINE_FAILED,
                message="medical08 backend not wired in stage 2; use constrained10",
                detail={"pipeline_backend": backend},
            )
        raise AppException(
            ErrorCode.PIPELINE_FAILED,
            message=f"unknown pipeline_backend={backend}",
        )

    def _mark_ready(self) -> None:
        RUNTIME.pipeline_loaded = True
        RUNTIME.pipeline_mode = self.config.retrieval_mode
        RUNTIME.pipeline_backend = self.config.pipeline_backend
        RUNTIME.last_error = None

    @staticmethod
    def _normalize_result(raw: Any) -> dict[str, Any]:
        if hasattr(raw, "to_dict") and callable(raw.to_dict):
            raw = raw.to_dict()
        if not isinstance(raw, dict):
            raise AppException(
                ErrorCode.PIPELINE_FAILED,
                detail=f"unexpected pipeline result type={type(raw).__name__}",
            )
        out = dict(raw)
        out.setdefault("answer", "")
        out.setdefault("sources", [])
        return out

    @staticmethod
    def _apply_top_k(pipeline: PipelineLike, top_k: int) -> dict[str, Any]:
        rp = getattr(pipeline, "retrieval_pipeline", None)
        if rp is not None and hasattr(rp, "top_k_final"):
            prev = getattr(rp, "top_k_final")
            rp.top_k_final = top_k
            return {"mode": "retrieval.top_k_final", "previous": prev}
        return {"mode": "truncate_sources", "previous": None}

    @staticmethod
    def _restore_top_k(pipeline: PipelineLike, restore: dict[str, Any]) -> None:
        if restore.get("mode") != "retrieval.top_k_final":
            return
        rp = getattr(pipeline, "retrieval_pipeline", None)
        if rp is not None and "previous" in restore:
            rp.top_k_final = restore["previous"]
