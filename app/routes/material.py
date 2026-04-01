from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.s3 import upload_file_to_s3, delete_file_from_s3, get_file_stream
from app.core.database import get_db
from app.models.material import Material
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.utils.check_filetype import check_pdf
from app.utils.filekey import filekey_gen
from app.core.config import settings

router = APIRouter()

def construct_material_url(base_url: str, material_id: int) -> str:
    clean_base = str(base_url).rstrip("/")
    return f"{clean_base}/api/materials/{material_id}/file"

class MaterialResponse(BaseModel):
    id: int
    name: str
    desc: Optional[str] = None
    materialUrl: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

def material_to_response(material: Material, base_url:str):
    return MaterialResponse(
        id=material.id,
        name=material.name,
        desc=material.desc,
        materialUrl=construct_material_url(base_url, material.id),
        created_at=material.created_at,
        updated_at=material.updated_at
    )

@router.post("/api/materials", response_model=MaterialResponse, status_code=201)
async def create_material(
    request: Request,
    name: str = Form(...),
    desc: str | None = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).where(Material.name == name)
    result = await db.execute(stmt)
    existing_material = result.scalar_one_or_none()
    
    if existing_material:
        raise HTTPException(status_code=400, detail="A material with this name already exists.")
    
    # validate file
    kind = await check_pdf(file)
    filekey = filekey_gen(prefix=settings.S3_MATERIAL_FOLDER, ext=kind.EXTENSION.lower())
    file_content_type = kind.MIME

    try:
        await upload_file_to_s3(file.file, filekey, file_content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail="File upload failed.")
    
    new_material = Material(
        name=name,
        desc=desc,
        filekey=filekey
    )
    
    db.add(new_material)
    try:
        await db.commit()
        await db.refresh(new_material)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="A material with this name already exists.")
    
    return material_to_response(new_material, str(request.base_url))

@router.get("/api/materials", response_model=list[MaterialResponse])
async def get_all_materials(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).order_by(Material.created_at.desc())
    result = await db.execute(stmt)

    materials = result.scalars().all()

    return [
        material_to_response(m, str(request.base_url))
        for m in materials
    ]

@router.get("/api/materials/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)

    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )
    
    return material_to_response(material, str(request.base_url))

@router.get("/api/materials/{material_id}/file")
async def stream_material_file(
    material_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)

    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )

    try:
        file_stream, content_type = await get_file_stream(material.filekey)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="File not found in storage"
        )

    return StreamingResponse(
        file_stream,
        media_type=content_type,
        headers={
            "Content-Disposition":
            f'inline; filename="{material.name}.pdf"'
        }
    )

@router.patch("/api/materials/{material_id}", response_model=MaterialResponse)
async def update_material(
    material_id: int,
    request: Request,
    name: str | None = Form(None),
    desc: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db)
):
    update_requested = any([
        name is not None,
        desc is not None,
        file is not None
    ])

    if not update_requested:
        raise HTTPException(
            400,
            "No update fields provided"
        )

    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)

    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )
    
    if name is not None:

        cleaned_name = name.strip()

        if cleaned_name == "":
            raise HTTPException(
                status_code=400,
                detail="Name cannot be empty"
            )

        stmt = select(Material).where(
            Material.name == cleaned_name,
            Material.id != material_id
        )

        result = await db.execute(stmt)

        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Material name already exists"
            )

        material.name = cleaned_name

    if desc is not None:
        cleaned_desc = desc.strip()
        material.desc = cleaned_desc if cleaned_desc else None

    old_filekey = None

    if file:
        kind = await check_pdf(file)

        new_filekey = filekey_gen(
            prefix=settings.S3_MATERIAL_FOLDER,
            ext=kind.EXTENSION.lower()
        )

        old_filekey = material.filekey

        try:
            await upload_file_to_s3(
                file.file,
                new_filekey,
                kind.MIME
            )

            material.filekey = new_filekey

        except Exception:
            raise HTTPException(
                status_code=500,
                detail="File update failed"
            )

    try:
        await db.commit()
        await db.refresh(material)

        if old_filekey:
            await delete_file_from_s3(old_filekey)

    except IntegrityError:
        await db.rollback()

        raise HTTPException(
            status_code=400,
            detail="Material name already exists"
        )

    return material_to_response(material, str(request.base_url))

@router.delete("/api/materials/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).where(Material.id == material_id)
    result = await db.execute(stmt)

    material = result.scalar_one_or_none()

    if not material:
        raise HTTPException(
            status_code=404,
            detail="Material not found"
        )

    try:
        await delete_file_from_s3(material.filekey)
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Failed to delete file from storage"
        )

    await db.delete(material)
    await db.commit()

    return None