from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.core.config import settings
from app.routes import material, video, quiz

app = FastAPI(
    title=settings.APP_NAME
)

@app.get("/")
def read_root():
    return FileResponse("templates/index.html")

@app.get("/favicon.ico")
@app.get("/favicon.png")
def get_favicon():
    return FileResponse("assets/favicon.png")

@app.get("/health")
def check_health():
    return {"success": True}

app.include_router(material.router)
app.include_router(video.router)
app.include_router(quiz.router)