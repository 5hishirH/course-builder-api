from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.core.s3 import upload_file_to_s3
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
    
    material_url = construct_material_url(str(request.base_url), new_material.id)
    
    return MaterialResponse(
        id=new_material.id,
        name=new_material.name,
        desc=new_material.desc,
        materialUrl=material_url,
        created_at=new_material.created_at,
        updated_at=new_material.updated_at
    )

@router.get("/api/materials", response_model=list[MaterialResponse])
async def get_all_materials(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Material).order_by(Material.created_at.desc())
    result = await db.execute(stmt)

    materials = result.scalars().all()

    response = []

    for material in materials:
        material_url = construct_material_url(
            str(request.base_url),
            material.id
        )

        response.append(
            MaterialResponse(
                id=material.id,
                name=material.name,
                desc=material.desc,
                materialUrl=material_url,
                created_at=material.created_at,
                updated_at=material.updated_at
            )
        )

    return response