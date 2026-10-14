from fastapi import APIRouter, Header, HTTPException

from ai.sub2_relay import Sub2RelayService, relay_key_matches


router = APIRouter()
service = Sub2RelayService()


def _authorize(authorization):
    scheme, _, value = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not relay_key_matches(value):
        raise HTTPException(status_code=401, detail="relay authorization required")


@router.post("/internal/g4c/sub2/videos", status_code=202)
def create_sub2_video(payload: dict, authorization: str | None = Header(None),
                      idempotency_key: str | None = Header(None, alias="Idempotency-Key")):
    _authorize(authorization)
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    try:
        return service.create(idempotency_key, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409 if str(exc) == "REQUEST_DRIFT" else 400,
                            detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/internal/g4c/sub2/videos/{request_id}")
def get_sub2_video(request_id: str, authorization: str | None = Header(None)):
    _authorize(authorization)
    try:
        return service.status(request_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="relay request not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
