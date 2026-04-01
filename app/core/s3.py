import boto3
from botocore.exceptions import ClientError
from fastapi.concurrency import run_in_threadpool

from app.core.config import settings

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.S3_KEY_ID,
    aws_secret_access_key=settings.S3_ACCESS_KEY,
    endpoint_url=settings.S3_ENDPOINT,
    region_name=settings.S3_REGION    
)

def _upload_to_s3_sync(
    file_obj,
    bucket: str,
    filekey: str,
    content_type: str
):
    try:
        s3_client.upload_fileobj(
            file_obj, bucket,
            filekey,
            ExtraArgs={'ContentType': content_type}
        )
    except ClientError as e:
        raise Exception(f"Failed to upload to S3: {e}")

async def upload_file_to_s3(file_obj, filekey: str, content_type: str = "application/octet-stream") -> str:    
    await run_in_threadpool(
        _upload_to_s3_sync, 
        file_obj, 
        settings.S3_BUCKET_NAME, 
        filekey,
        content_type
    )
    
    return filekey
