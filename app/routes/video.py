from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, ConfigDict, HttpUrl
from datetime import datetime
from typing import Optional
from app.core.database import get_db
from app.models.video import Video
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

router = APIRouter()

class VideoCreate(BaseModel):
    name: str
    desc: Optional[str] = None
    url: HttpUrl

class VideoUpdate(BaseModel):
    name: Optional[str] = None
    desc: Optional[str] = None
    url: Optional[HttpUrl] = None

class VideoResponse(BaseModel):
    id: int
    name: str
    desc: Optional[str]
    url: HttpUrl
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

@router.post("/api/videos", response_model=VideoResponse, status_code=201)
async def create_video(
    payload: VideoCreate,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Video).where(Video.name == payload.name.strip())
    result = await db.execute(stmt)

    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Video with this name already exists"
        )

    video = Video(
        name=payload.name.strip(),
        desc=payload.desc.strip() if payload.desc else None,
        url=str(payload.url)
    )

    db.add(video)

    try:
        await db.commit()
        await db.refresh(video)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Video already exists"
        )

    return video

@router.get("/api/videos", response_model=list[VideoResponse])
async def get_all_videos(
    db: AsyncSession = Depends(get_db)
):

    stmt = select(Video).order_by(Video.created_at.desc())
    result = await db.execute(stmt)

    return result.scalars().all()

@router.get("/api/videos/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db)
):

    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)

    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    return video

@router.patch("/api/videos/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: int,
    payload: VideoUpdate,
    db: AsyncSession = Depends(get_db)
):

    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)

    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields provided for update"
        )
    
    if "name" in update_data:

        cleaned_name = update_data["name"].strip()

        if cleaned_name == "":
            raise HTTPException(
                status_code=400,
                detail="Name cannot be empty"
            )

        stmt = select(Video).where(
            Video.name == cleaned_name,
            Video.id != video_id
        )

        result = await db.execute(stmt)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Video name already exists"
            )

        video.name = cleaned_name

    if "desc" in update_data:

        desc = update_data["desc"]

        video.desc = desc.strip() if desc else None
        
    if "url" in update_data:
        video.url = str(update_data["url"])

    try:
        await db.commit()
        await db.refresh(video)

    except IntegrityError:

        await db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Video update failed"
        )

    return video

@router.delete("/api/videos/{video_id}", status_code=204)
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db)
):

    stmt = select(Video).where(Video.id == video_id)
    result = await db.execute(stmt)

    video = result.scalar_one_or_none()

    if not video:
        raise HTTPException(
            status_code=404,
            detail="Video not found"
        )

    await db.delete(video)
    await db.commit()

    return None
