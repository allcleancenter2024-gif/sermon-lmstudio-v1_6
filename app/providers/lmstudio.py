"""LM Studio OpenAI-compatible local provider."""

from __future__ import annotations

import http.client
import json
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.config import get_lmstudio_url, normalize_lmstudio_url
from app.lmstudio_control import loaded_model_ids

@dataclass
class LMStudioClient:
    base_url: str | None = None
    # Long local generations are streamed. This is therefore an inactivity
    # timeout (including prompt ingestion), not a whole-generation deadline.
    timeout: int = 900

    def __post_init__(self) -> None:
        self.base_url = normalize_lmstudio_url(self.base_url) if self.base_url else get_lmstudio_url()

    def _request_url(self, method: str, url: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                detail = ""
            if exc.code == 400 and ("exceed_context_size" in detail or "exceeds the available context size" in detail):
                prompt_match = re.search(r'prompt_tokens[\\\"]*[:=]\\?"?(\d+)', detail)
                ctx_match = re.search(r'(?:n_ctx|context size)[\\\"]*[:= ]+\\?"?(\d+)', detail)
                prompt_tokens = prompt_match.group(1) if prompt_match else "현재 요청"
                context_tokens = ctx_match.group(1) if ctx_match else "현재 모델"
                raise ConnectionError(
                    f"LM Studio 컨텍스트 한도 초과: 입력 {prompt_tokens} tokens / 모델 한도 {context_tokens} tokens. "
                    "근거자료는 자동 축약되지만 계속 발생하면 LM Studio에서 더 큰 Context Length로 모델을 다시 로드하세요."
                ) from exc
            raise ConnectionError(f"LM Studio API HTTP {exc.code}: {detail or url}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionResetError,
                BrokenPipeError, http.client.RemoteDisconnected) as exc:
            if "/chat/completions" in url:
                raise ConnectionError(
                    f"LM Studio 실제 추론 연결이 끊겼습니다: {url}. "
                    "LM Studio 0.4.x의 Developer > Local Server가 Running인지, 선택 모델이 Loaded Models에서 READY인지, "
                    "서버 주소/포트가 이 프로그램 설정과 같은지 확인한 뒤 Preflight를 다시 실행하세요."
                ) from exc
            raise ConnectionError(
                f"LM Studio에 연결할 수 없습니다: {url}. Local Server와 포트를 확인하세요."
            ) from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LM Studio가 JSON이 아닌 응답을 반환했습니다: {url}") from exc
        if not isinstance(result, dict):
            raise RuntimeError(f"LM Studio 응답이 JSON 객체 형식이 아닙니다: {url}")
        return result

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        return self._request_url(method, self.base_url.rstrip("/") + path, payload)

    def _loaded_model_ids(self) -> set[str] | None:
        return loaded_model_ids()

    @staticmethod
    def _model_ids(result: dict) -> list[str]:
        items = result.get("data")
        if not isinstance(items, list):
            items = result.get("models")
        if not isinstance(items, list):
            return []
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            model_id = str(item.get("id") or item.get("key") or "").strip() if isinstance(item, dict) else ""
            if model_id and model_id not in seen:
                seen.add(model_id)
                output.append(model_id)
        return output

    @staticmethod
    def _is_embedding_model(model_id: str) -> bool:
        value = model_id.lower()
        hints = ("embedding", "embed", "bge-", "bge_", "e5-", "e5_", "gte-", "gte_", "nomic-embed")
        return any(hint in value for hint in hints)

    def model_catalog(self) -> dict:
        warnings: list[str] = []
        openai_error = ""
        try:
            openai_models = self._model_ids(self._request("GET", "/models"))
        except (ConnectionError, RuntimeError) as exc:
            openai_models = []
            openai_error = str(exc)
        if openai_models:
            models = openai_models
            source = "openai_compatible"
            loaded = self._loaded_model_ids()
            if loaded is not None:
                confirmed = [model for model in models if model in loaded]
                if confirmed:
                    omitted = len(models) - len(confirmed)
                    models = confirmed
                    if omitted:
                        warnings.append(f"lms ps 기준 실제 로드되지 않은 모델 {omitted}개를 선택 목록에서 제외했습니다.")
                elif loaded:
                    warnings.append("lms ps 모델 식별자와 /v1/models 식별자가 달라 실제 추론 Preflight에서 최종 확인합니다.")
        else:
            if not openai_error:
                openai_error = "GET /v1/models 응답에서 모델 목록(data)을 찾지 못했습니다."
            native_url = self.base_url[:-3] + "/api/v1/models"
            try:
                models = self._model_ids(self._request_url("GET", native_url))
            except (ConnectionError, RuntimeError) as exc:
                models = []
                warnings.append(f"LM Studio REST API 진단도 실패했습니다: {exc}")
            source = "native_model_fallback" if models else "unavailable"
            if models:
                warnings.append("/api/v1/models 보조 목록입니다. 설치된 모델이 포함될 수 있으므로 LM Studio의 Loaded Models에서 READY 여부를 확인하세요.")
        embedding_models = [m for m in models if self._is_embedding_model(m)]
        generation_models = [m for m in models if m not in embedding_models]
        return {
            "models": models,
            "generation_models": generation_models,
            "embedding_models": embedding_models,
            "source": source,
            "openai_models_ok": source == "openai_compatible",
            "openai_error": openai_error,
            "warnings": warnings,
        }

    def models(self) -> list[str]:
        return self.model_catalog()["models"]

    def _inference_request_with_retry(self, payload: dict, retries: int = 1) -> dict:
        """Retry only a transport failure; never retry HTTP/model/context errors."""
        last_error: ConnectionError | None = None
        for attempt in range(retries + 1):
            try:
                return self._request("POST", "/chat/completions", payload)
            except ConnectionError as exc:
                last_error = exc
                message = str(exc)
                transient = "실제 추론 연결이 끊겼습니다" in message
                if not transient or attempt >= retries:
                    raise
                time.sleep(0.8)
                catalog = self.model_catalog()
                model = str(payload.get("model", ""))
                if catalog.get("source") != "openai_compatible":
                    raise ConnectionError(
                        "LM Studio 서버 재연결에 실패했습니다. Developer > Local Server를 Running으로 켜고 "
                        f"API 주소를 {self.base_url}로 맞춘 뒤 연결 복구 점검을 실행하세요."
                    ) from exc
                if model not in (catalog.get("generation_models") or []):
                    raise ConnectionError(
                        f"연결은 복구됐지만 선택 모델이 READY 목록에 없습니다: {model}. "
                        "LM Studio Loaded Models에서 모델을 다시 Load한 뒤 READY를 확인하세요."
                    ) from exc
        raise last_error or ConnectionError("LM Studio 추론 연결에 실패했습니다.")

    @staticmethod
    def _stream_piece(event: dict) -> str:
        try:
            choice = event["choices"][0]
        except (KeyError, IndexError, TypeError):
            return ""
        delta = choice.get("delta") if isinstance(choice, dict) else None
        if isinstance(delta, dict) and isinstance(delta.get("content"), str):
            return delta["content"]
        message = choice.get("message") if isinstance(choice, dict) else None
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        return choice.get("text", "") if isinstance(choice, dict) and isinstance(choice.get("text"), str) else ""

    def _stream_chat_once(self, payload: dict) -> str:
        """Collect an OpenAI-compatible SSE response without a whole-job timeout."""
        url = self.base_url.rstrip("/") + "/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps({**payload, "stream": True}).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        )
        pieces: list[str] = []
        reasoning_seen = False
        finish_reason = ""
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                content_type = str(response.headers.get("Content-Type", "")).lower()
                if "text/event-stream" not in content_type:
                    raw = response.read().decode("utf-8")
                    try:
                        result = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError("LM Studio가 JSON/SSE가 아닌 응답을 반환했습니다.") from exc
                    text = self._stream_piece(result) if isinstance(result, dict) else ""
                    if not text:
                        raise RuntimeError("LM Studio 응답 형식을 해석하지 못했습니다.")
                    return text
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        try:
                            choice = event["choices"][0]
                            delta = choice.get("delta") if isinstance(choice, dict) else None
                            reasoning_seen = reasoning_seen or bool(
                                isinstance(delta, dict)
                                and (delta.get("reasoning_content") or delta.get("reasoning"))
                            )
                            finish_reason = str(choice.get("finish_reason") or finish_reason)
                        except (KeyError, IndexError, TypeError):
                            pass
                        piece = self._stream_piece(event)
                        if piece:
                            pieces.append(piece)
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            if exc.code == 400 and ("exceed_context_size" in detail or "exceeds the available context size" in detail):
                prompt_match = re.search(r'(?:n_prompt_tokens[\\\"]*[:=]\\?"?|request \\?\()(\d+)', detail)
                ctx_match = re.search(r'(?:n_ctx[\\\"]*[:= ]+\\?"?|context size \\?\()(\d+)', detail)
                prompt_tokens = prompt_match.group(1) if prompt_match else "현재 요청"
                context_tokens = ctx_match.group(1) if ctx_match else "현재 모델"
                raise ConnectionError(
                    f"LM Studio 컨텍스트 한도 초과: 입력 {prompt_tokens} tokens / 모델 한도 {context_tokens} tokens. "
                    "근거자료를 줄이거나 LM Studio에서 더 큰 Context Length로 모델을 다시 로드하세요."
                ) from exc
            raise ConnectionError(f"LM Studio API HTTP {exc.code}: {detail or url}") from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout, ConnectionResetError,
                BrokenPipeError, http.client.RemoteDisconnected) as exc:
            if pieces:
                raise ConnectionError(
                    "LM Studio가 생성 중 일부 토큰을 보낸 뒤 연결이 끊겼습니다. 부분 설교를 저장하지 않았습니다. "
                    "모델이 계속 READY인지 확인하고 다시 생성하세요."
                ) from exc
            raise ConnectionError(
                f"LM Studio 실제 추론 연결이 끊겼습니다: {url}. Local Server와 READY 모델을 확인하세요."
            ) from exc
        text = "".join(pieces).strip()
        if not text:
            if reasoning_seen:
                suffix = f" 종료 이유: {finish_reason}." if finish_reason else ""
                raise RuntimeError(
                    "LM Studio가 내부 추론만 생성하고 최종 본문을 반환하지 않았습니다."
                    f"{suffix} 모델의 추론 토큰 제한을 늘리거나 Thinking을 끈 뒤 다시 시도하세요."
                )
            raise RuntimeError("LM Studio 스트리밍 응답에 생성된 본문이 없습니다.")
        return text

    def chat(
        self, model: str, system: str, user: str, temperature: float = 0.35,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        # LM Studio may otherwise apply a small server-side default. On
        # reasoning models that budget can be consumed by Thinking before the
        # requested answer is emitted, so reserve an explicit answer budget.
        payload["max_tokens"] = max(1, int(max_tokens)) if max_tokens is not None else 4096
        last_error: ConnectionError | None = None
        for attempt in range(2):
            try:
                return self._stream_chat_once(payload)
            except RuntimeError as exc:
                # Qwen3/Qwen3.5-compatible templates can return only
                # reasoning_content when Thinking is enabled. Never expose
                # that internal trace as a sermon; retry once with the
                # LM Studio-supported template switch that requests answer
                # content directly. The retry is deliberately limited to this
                # exact condition so malformed responses and other failures
                # remain actionable instead of being hidden.
                if "내부 추론만 생성" not in str(exc) or payload.get("chat_template_kwargs"):
                    raise
                payload = {
                    **payload,
                    "chat_template_kwargs": {"enable_thinking": False},
                    "max_tokens": max(int(payload.get("max_tokens", 4096)), 4096),
                }
                continue
            except ConnectionError as exc:
                last_error = exc
                transient = "실제 추론 연결이 끊겼습니다" in str(exc)
                if not transient or attempt:
                    raise
                time.sleep(0.8)
                catalog = self.model_catalog()
                if model not in (catalog.get("generation_models") or []):
                    raise ConnectionError(f"연결 재확인 후 선택 모델이 READY 목록에 없습니다: {model}.") from exc
        raise last_error or ConnectionError("LM Studio 추론 연결에 실패했습니다.")

    def probe_generation(self, model: str) -> None:
        """Verify that the selected model can actually run inference, not just appear in /models."""
        result = self._inference_request_with_retry(
            {
                "model": model,
                "messages": [{"role": "user", "content": "OK"}],
                "temperature": 0,
                "max_tokens": 1,
                "stream": False,
            }, retries=1,
        )
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("LM Studio 추론 점검 응답에 choices가 없습니다. 모델을 다시 로드하세요.")

    def embeddings(self, model: str, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        result = self._request("POST", "/embeddings", {"model": model, "input": texts})
        try:
            ordered = sorted(result["data"], key=lambda item: int(item.get("index", 0)))
            vectors = [[float(x) for x in item["embedding"]] for item in ordered]
            if len(vectors) != len(texts):
                raise ValueError("embedding count mismatch")
            return vectors
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("LM Studio 임베딩 응답 형식을 해석하지 못했습니다.") from exc
