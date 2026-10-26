from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..deps import get_db, get_household_id
from ..models import Member
from ..schemas import MemberIn
from ..services import member_view, validated_targets

router = APIRouter(prefix="/api/members", tags=["members"])
MAX_MEMBERS = 8


def _get(db: Session, member_id: int, household_id: int) -> Member:
    member = db.scalar(select(Member).where(Member.id == member_id, Member.household_id == household_id))
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


@router.get("")
def list_members(db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    rows = db.scalars(select(Member).where(Member.household_id == household_id).order_by(Member.id))
    return [member_view(m) for m in rows]


@router.post("", status_code=201)
def create_member(body: MemberIn, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    count = db.scalar(select(func.count()).select_from(Member).where(Member.household_id == household_id))
    if count >= MAX_MEMBERS:
        raise HTTPException(status_code=409, detail=f"A household can have at most {MAX_MEMBERS} members")
    validated_targets(body)
    member = Member(household_id=household_id, **body.model_dump())
    db.add(member)
    db.commit()
    return member_view(member)


@router.get("/{member_id}")
def get_member(member_id: int, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    return member_view(_get(db, member_id, household_id))


@router.put("/{member_id}")
def update_member(
    member_id: int, body: MemberIn, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)
):
    member = _get(db, member_id, household_id)
    validated_targets(body)
    for key, value in body.model_dump().items():
        setattr(member, key, value)
    db.commit()
    return member_view(member)


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: int, db: Session = Depends(get_db), household_id: int = Depends(get_household_id)):
    db.delete(_get(db, member_id, household_id))
    db.commit()
