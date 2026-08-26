from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, Base, get_db

# Tự động tạo bảng Database
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

# Cấu hình Static và Templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home_page(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "app_name": settings.APP_NAME,
            "db_status": "SQLite Connected"
        }
    )

@app.get("/healthcheck")
def health_check(db: Session = Depends(get_db)):
    return {"status": "ok", "app_name": settings.APP_NAME, "database": "connected"}