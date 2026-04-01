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
            file_obj,
            bucket,
            filekey,
            ExtraArgs={'ContentType': content_type}
        )
    except ClientError as e:
        raise Exception(f"Failed to upload to S3: {e}")
    
def _get_file_stream(filekey: str):
    response = s3_client.get_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=filekey
    )

    return response["Body"], response["ContentType"]
    
def _delete_file_from_s3(objkey: str):
    s3_client.delete_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=objkey
    )

async def upload_file_to_s3(file_obj, filekey: str, content_type: str = "application/octet-stream") -> str:    
    await run_in_threadpool(
        _upload_to_s3_sync, 
        file_obj, 
        settings.S3_BUCKET_NAME, 
        filekey,
        content_type
    )
    
    return filekey

async def get_file_stream(filekey: str):
    return await run_in_threadpool(
        _get_file_stream,
        filekey
    )

async def delete_file_from_s3(filekey: str) -> str:
    await run_in_threadpool(
        _delete_file_from_s3,
        filekey
    )

    return filekey
