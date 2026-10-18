from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import CommunicationProfile, UserProfile
from app.schemas import (
    CommunicationProfileRead,
    CommunicationProfileUpdate,
    UserProfileRead,
    UserProfileUpdate,
)

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


async def _get_or_create_profile(session: SessionDep, user_id) -> UserProfile:
    profile = await session.scalar(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    if profile is None:
        profile = UserProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


async def _get_or_create_communication(session: SessionDep, user_id) -> CommunicationProfile:
    profile = await session.scalar(
        select(CommunicationProfile).where(CommunicationProfile.user_id == user_id)
    )
    if profile is None:
        profile = CommunicationProfile(user_id=user_id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


@router.get("", response_model=UserProfileRead)
async def read_profile(session: SessionDep, user: CurrentUser) -> UserProfile:
    return await _get_or_create_profile(session, user.id)


@router.patch("", response_model=UserProfileRead)
async def update_profile(
    payload: UserProfileUpdate, session: SessionDep, user: CurrentUser
) -> UserProfile:
    profile = await _get_or_create_profile(session, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.profile_version += 1
    await session.commit()
    await session.refresh(profile)
    return profile


@router.get("/communication", response_model=CommunicationProfileRead)
async def read_communication_profile(
    session: SessionDep, user: CurrentUser
) -> CommunicationProfile:
    return await _get_or_create_communication(session, user.id)


@router.patch("/communication", response_model=CommunicationProfileRead)
async def update_communication_profile(
    payload: CommunicationProfileUpdate, session: SessionDep, user: CurrentUser
) -> CommunicationProfile:
    profile = await _get_or_create_communication(session, user.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    profile.version += 1
    await session.commit()
    await session.refresh(profile)
    return profile
