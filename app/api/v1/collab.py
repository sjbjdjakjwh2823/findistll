from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.auth import CurrentUser, get_current_user
from app.db.registry import get_db
from app.services.enterprise_collab import EnterpriseCollabStore


router = APIRouter(prefix="/collab", tags=["Enterprise Collaboration"])


class ContactRequestIn(BaseModel):
    target_user_id: str


class ContactAcceptIn(BaseModel):
    contact_id: str


class TeamCreateIn(BaseModel):
    name: str


class TeamMemberAddIn(BaseModel):
    user_id: str
    role: str = Field(default="member")


class SpaceCreateIn(BaseModel):
    type: str = Field(default="personal")
    name: str
    team_id: Optional[str] = None


class SpaceUpdateIn(BaseModel):
    name: str


class FileUploadIn(BaseModel):
    space_id: str
    doc_id: str
    version: int = 1
    visibility: str = "private"


class FileShareIn(BaseModel):
    principal_type: str = Field(description="user|team")
    principal_id: str
    permission: str = Field(default="read", description="read|comment|share")


class TransferSendIn(BaseModel):
    receiver_user_id: str
    file_id: str
    message: Optional[str] = None


class TransferAckIn(BaseModel):
    status: str = Field(default="read", description="read|accepted|rejected")


class InviteCreateIn(BaseModel):
    target_user_id: Optional[str] = None


class InviteAcceptIn(BaseModel):
    code: str


def _store() -> EnterpriseCollabStore:
    return EnterpriseCollabStore(get_db())


def _as_http_error(exc: Exception) -> HTTPException:
    message = str(exc)
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=message)
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=message)
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=message)
    return HTTPException(status_code=500, detail=message)


@router.post("/contacts/request")
def request_contact(
    payload: ContactRequestIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().request_contact(
            requester_user_id=user.user_id,
            target_user_id=payload.target_user_id,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/contacts/accept")
def accept_contact(
    payload: ContactAcceptIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().accept_contact(
            current_user_id=user.user_id,
            contact_id=payload.contact_id,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/contacts/list")
def list_contacts(user: CurrentUser = Depends(get_current_user)):
    try:
        return {"items": _store().list_contacts(current_user_id=user.user_id)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/invites/create")
def create_invite(payload: InviteCreateIn, user: CurrentUser = Depends(get_current_user)):
    try:
        return _store().create_invite(requester_user_id=user.user_id, target_user_id=payload.target_user_id)
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/invites/accept")
def accept_invite(payload: InviteAcceptIn, user: CurrentUser = Depends(get_current_user)):
    try:
        return _store().accept_invite(current_user_id=user.user_id, code=payload.code)
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/invites/list")
def list_invites(user: CurrentUser = Depends(get_current_user)):
    try:
        return {"items": _store().list_invites(requester_user_id=user.user_id)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/teams")
def create_team(
    payload: TeamCreateIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().create_team(owner_user_id=user.user_id, name=payload.name)
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/teams/{team_id}/members")
def add_team_member(
    team_id: str,
    payload: TeamMemberAddIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().add_team_member(
            actor_user_id=user.user_id,
            team_id=team_id,
            user_id=payload.user_id,
            role=payload.role,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/teams/my-teams")
def list_my_teams(user: CurrentUser = Depends(get_current_user)):
    try:
        return {"items": _store().list_my_teams(user_id=user.user_id)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/spaces")
def create_space(
    payload: SpaceCreateIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().create_space(
            actor_user_id=user.user_id,
            space_type=payload.type,
            name=payload.name,
            team_id=payload.team_id,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/spaces")
def list_spaces(user: CurrentUser = Depends(get_current_user)):
    try:
        return {"items": _store().list_spaces(user_id=user.user_id)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.patch("/spaces/{space_id}")
def patch_space(
    space_id: str,
    payload: SpaceUpdateIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().update_space(
            actor_user_id=user.user_id,
            space_id=space_id,
            name=payload.name,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/files/upload")
def register_file(
    payload: FileUploadIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().register_file(
            actor_user_id=user.user_id,
            space_id=payload.space_id,
            doc_id=payload.doc_id,
            version=payload.version,
            visibility=payload.visibility,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/files")
def list_files(
    limit: int = Query(default=100, ge=1, le=500),
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return {"items": _store().list_files(user_id=user.user_id, role=user.role, limit=limit)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/files/{file_id}")
def get_file(
    file_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        store = _store()
        if not store.can_read_file(user_id=user.user_id, role=user.role, file_id=file_id):
            raise PermissionError("file access denied")
        file_row = store.get_file(file_id=file_id)
        return {"item": file_row}
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/files/{file_id}/share")
def share_file(
    file_id: str,
    payload: FileShareIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().share_file(
            actor_user_id=user.user_id,
            file_id=file_id,
            principal_type=payload.principal_type,
            principal_id=payload.principal_id,
            permission=payload.permission,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/transfers/send")
def send_transfer(
    payload: TransferSendIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().send_transfer(
            sender_user_id=user.user_id,
            receiver_user_id=payload.receiver_user_id,
            file_id=payload.file_id,
            message=payload.message,
        )
    except Exception as exc:
        raise _as_http_error(exc)


@router.get("/transfers/inbox")
def list_inbox(user: CurrentUser = Depends(get_current_user)):
    try:
        return {"items": _store().list_inbox(user_id=user.user_id)}
    except Exception as exc:
        raise _as_http_error(exc)


@router.post("/transfers/{transfer_id}/ack")
def ack_transfer(
    transfer_id: str,
    payload: TransferAckIn,
    user: CurrentUser = Depends(get_current_user),
):
    try:
        return _store().ack_transfer(
            user_id=user.user_id,
            transfer_id=transfer_id,
            status=payload.status,
        )
    except Exception as exc:
        raise _as_http_error(exc)
