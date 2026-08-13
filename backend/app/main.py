from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import init_db

from app.api import health, datasets
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

@app.on_event("startup")
def on_startup():
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(datasets.router)


@app.get("/")
def root():
    return {"message": f"{settings.app_name} is running. See /docs for API docs."}