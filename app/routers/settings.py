from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.application.settings_facade import (
    LMStudioClient, calibrate_reading_cpm, find_lms_cli, get_github_repository_url,
    get_lmstudio_url, get_reading_cpm, local_api_port, port_is_open,
    set_github_repository_url, set_lmstudio_url, set_reading_cpm, start_local_server,
)

router = APIRouter()

class ReadingSpeedRequest(BaseModel):
    chars_per_minute: int = Field(ge=180, le=600)
class LMStudioSettingsRequest(BaseModel):
    base_url: str = Field(default="http://127.0.0.1:12345/v1", min_length=10, max_length=300)
class LMStudioRecoveryRequest(BaseModel):
    model: str = Field(default="", max_length=300)
class ReadingCalibrationRequest(BaseModel):
    text: str = Field(min_length=80, max_length=10000)
    seconds: float = Field(ge=15, le=3600)
class GitHubSettingsRequest(BaseModel):
    repository_url: str = Field(default="", max_length=300)

@router.get("/api/settings/github")
def github_settings():
    return {"repository_url": get_github_repository_url()}

@router.put("/api/settings/github")
def update_github_settings(data: GitHubSettingsRequest):
    try:
        return {"ok": True, "repository_url": set_github_repository_url(data.repository_url)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

@router.get("/api/settings/lmstudio")
def lmstudio_settings(): return {"base_url": get_lmstudio_url()}

@router.post("/api/lmstudio/recover")
def recover_lmstudio(data: LMStudioRecoveryRequest):
    client=LMStudioClient(timeout=20); steps=[]
    try:
        catalog=client.model_catalog(); openai_ok=catalog.get("source")=="openai_compatible"; steps.append({"key":"server","ok":openai_ok,"label":"Local Server","detail":"OpenAI 호환 /v1/models 응답 정상" if openai_ok else (catalog.get("openai_error") or "OpenAI 호환 모델 목록을 읽지 못했습니다.")}); generation=catalog.get("generation_models") or []; model=data.model.strip(); model_ok=bool(model and model in generation); steps.append({"key":"model","ok":model_ok,"label":"생성 모델","detail":f"READY · {model}" if model_ok else ("화면에서 READY 생성 모델을 다시 선택하세요." if generation else "LM Studio Loaded Models에 READY 생성 모델이 없습니다.")})
        if not openai_ok or not model_ok: return {"ok":False,"ready":False,"base_url":get_lmstudio_url(),"steps":steps,"generation_models":generation,"message":"LM Studio 설정을 확인한 뒤 다시 점검하세요."}
        client.probe_generation(model); steps.append({"key":"inference","ok":True,"label":"실제 추론","detail":"/v1/chat/completions 응답 정상"}); return {"ok":True,"ready":True,"base_url":get_lmstudio_url(),"steps":steps,"generation_models":generation,"model":model,"message":"실제 추론 연결이 복구되었습니다. Preflight를 다시 실행하세요."}
    except (ConnectionError,RuntimeError) as exc: steps.append({"key":"inference","ok":False,"label":"실제 추론","detail":str(exc)}); return {"ok":False,"ready":False,"base_url":get_lmstudio_url(),"steps":steps,"generation_models":[],"message":str(exc)}

@router.post("/api/lmstudio/start")
def start_lmstudio_server():
    base_url=get_lmstudio_url()
    try:
        result=start_local_server(base_url); result["base_url"]=base_url; result["ok"]=bool(result.get("port_open"))
        if result["port_open"]:
            try:
                catalog=LMStudioClient(base_url=base_url,timeout=5).model_catalog(); result["api_ready"]=catalog.get("source")=="openai_compatible"; result["generation_models"]=catalog.get("generation_models") or []
                if not result["api_ready"]: result["message"] += " 포트는 열렸지만 OpenAI 호환 /v1/models 응답이 아닙니다."
                elif not result["generation_models"]: result["message"] += " 서버는 정상이며, 이제 LM Studio에서 생성 모델을 Load해야 합니다."
            except (ConnectionError,RuntimeError) as exc: result.update({"api_ready":False,"generation_models":[]}); result["message"] += f" API 확인 실패: {exc}"
        else: result.update({"api_ready":False,"generation_models":[]})
        return result
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc

@router.get("/api/lmstudio/diagnostics")
def lmstudio_diagnostics():
    base_url=get_lmstudio_url()
    try: port=local_api_port(base_url)
    except ValueError as exc: return {"ok":False,"base_url":base_url,"cli_found":False,"port_open":False,"cause":"invalid_url","message":str(exc)}
    cli=find_lms_cli(); opened=port_is_open(port); cause="unknown"; message="LM Studio API를 확인할 수 없습니다."
    if not opened and cli is None: cause,message="cli_missing","LM Studio CLI를 찾지 못했습니다. LM Studio를 설치하고 한 번 실행하세요."
    elif not opened: cause,message="server_stopped","LM Studio는 설치되어 있지만 Local Server 포트가 닫혀 있습니다. 자동 시작 버튼을 누르세요."
    else:
        try:
            catalog=LMStudioClient(base_url=base_url,timeout=5).model_catalog(); generation=catalog.get("generation_models") or []
            if catalog.get("source")!="openai_compatible": cause,message="wrong_service",f"포트 {port}는 열렸지만 LM Studio OpenAI 호환 API가 아닙니다."
            elif not generation: cause,message="model_not_loaded","Local Server는 정상이나 READY 생성 모델이 없습니다. LM Studio에서 모델을 Load하세요."
            else: cause,message="ready",f"Local Server와 READY 생성 모델 {len(generation)}개를 확인했습니다."
            return {"ok":cause=="ready","base_url":base_url,"cli_found":cli is not None,"cli":str(cli or ""),"port":port,"port_open":True,"cause":cause,"generation_models":generation,"message":message}
        except (ConnectionError,RuntimeError) as exc: cause,message="api_error",str(exc)
    return {"ok":False,"base_url":base_url,"cli_found":cli is not None,"cli":str(cli or ""),"port":port,"port_open":opened,"cause":cause,"generation_models":[],"message":message}

@router.put("/api/settings/lmstudio")
def update_lmstudio_settings(data: LMStudioSettingsRequest):
    try:
        base_url=set_lmstudio_url(data.base_url); catalog=LMStudioClient(base_url=base_url,timeout=5).model_catalog(); return {"ok":True,"connected":bool(catalog["models"]),"base_url":base_url,**catalog}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
    except ConnectionError as exc: return {"ok":True,"connected":False,"base_url":get_lmstudio_url(),"models":[],"message":str(exc)}

@router.get("/api/settings/reading-speed")
def reading_speed(): return {"chars_per_minute":get_reading_cpm()}
@router.put("/api/settings/reading-speed")
def update_reading_speed(data: ReadingSpeedRequest): return {"ok":True,"chars_per_minute":set_reading_cpm(data.chars_per_minute)}
@router.post("/api/settings/reading-speed/calibrate")
def calibrate_speed(data: ReadingCalibrationRequest):
    try: return {"ok":True,"chars_per_minute":calibrate_reading_cpm(data.text,data.seconds)}
    except ValueError as exc: raise HTTPException(400,str(exc)) from exc
