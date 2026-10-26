"""Operator endpoints. Disabled unless ADMIN_TOKEN is set. The token only unlocks feature flags."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from ..schemas import FlagIn
from ..security import tokens_match

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    expected = request.app.state.settings.admin_token
    if expected is None:
        raise HTTPException(status_code=404, detail="Not found")
    if not tokens_match(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.get("/flags", dependencies=[Depends(require_admin)])
def list_flags(request: Request):
    return request.app.state.flags.all()


@router.put("/flags/{name}", dependencies=[Depends(require_admin)])
def set_flag(name: str, body: FlagIn, request: Request):
    if not request.app.state.flags.set(name, body.enabled):
        raise HTTPException(status_code=404, detail="Unknown flag")
    return {"name": name, "enabled": body.enabled}
