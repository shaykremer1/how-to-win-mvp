from fastapi import APIRouter, HTTPException

from backend.app.schemas.admin import ImportMatchIn, ImportMatchOut, MatchDataSummaryOut
from backend.app.services.admin import delete_match_data, get_match_data_summary, import_match

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/import-match", response_model=ImportMatchOut)
def import_match_endpoint(payload: ImportMatchIn):
    result = import_match(payload)
    if result.returncode != 0:
        raise HTTPException(status_code=400, detail={"stdout": result.stdout, "stderr": result.stderr})
    return result


@router.get("/match/{match_id}/summary", response_model=MatchDataSummaryOut)
def match_summary(match_id: int):
    return get_match_data_summary(match_id)


@router.delete("/match/{match_id}")
def delete_match(match_id: int):
    delete_match_data(match_id)
    return {"status": "deleted", "match_id": match_id}
