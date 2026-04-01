import uuid

def filekey_gen(prefix: str, ext: str) -> str:
    clean_prefix = str(prefix).rstrip("/")
    unique_id = uuid.uuid4()

    return f"{clean_prefix}/{unique_id}.{ext}"
