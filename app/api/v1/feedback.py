from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from app.core.auth import get_current_user
from app.db.registry import get_db

router = APIRouter(tags=['feedback'])


class FeedbackRequest(BaseModel):
    score: int
    comment: Optional[str] = None
    case_id: Optional[str] = None


@router.post('/evidence/{evidence_id}/feedback')
async def submit_feedback(evidence_id: str, payload: FeedbackRequest, current_user = Depends(get_current_user)):
    record = {
        'evidence_id': evidence_id,
        'case_id': payload.case_id,
        'user_id': current_user.user_id,
        'score': payload.score,
        'comment': payload.comment,
    }
    get_db().save_evidence_feedback(record)
    return {'status': 'success'}


@router.get('/cases/{case_id}/feedback-summary')
async def feedback_summary(case_id: str):
    return get_db().get_feedback_summary(case_id)
