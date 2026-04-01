import filetype
from fastapi import UploadFile, HTTPException, status
from fastapi.concurrency import run_in_threadpool

def validate_file_type(file: UploadFile, allowed_mimes: list[str]):
    header = file.file.read(261)
    file.file.seek(0)
    
    kind = filetype.guess(header)

    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Could not determine file type."
        )
    
    if kind.mime not in allowed_mimes:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_mimes)}"
        )
    
    return kind


async def check_pdf(file: UploadFile):
    return await run_in_threadpool(
        validate_file_type,
        file,
        ["application/pdf"]
    ) 