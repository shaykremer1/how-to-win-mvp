from fastapi import APIRouter

from backend.app.schemas.common import MatchOut
from backend.app.services.matches import fetch_matches_for_dropdown, make_match_label

router = APIRouter(prefix="/matches", tags=["matches"])


@router.get("", response_model=list[MatchOut])
def list_matches():
    df = fetch_matches_for_dropdown()
    if df.empty:
        return []

    df = df.copy()
    df["label"] = df.apply(make_match_label, axis=1)

    out = []
    for _, row in df.iterrows():
        out.append(
            MatchOut(
                match_id=int(row["match_id"]),
                match_name=row["match_name"] if row["match_name"] is not None else None,
                match_date=str(row["match_date"]) if row["match_date"] is not None else None,
                label=str(row["label"]),
            )
        )
    return out
