import os
import time
import logging

from fastapi import FastAPI, Request, Response
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi.middleware.cors import CORSMiddleware

from db import database, DATABASE_URL
from api import router
from models import metadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("app")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)
async_engine = create_async_engine(ASYNC_DATABASE_URL, future=True)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    logger.info(
        "→ Request %s %s Headers=%s",
        request.method,
        request.url.path,
        dict(request.headers),
    )
    response = await call_next(request)
    process_time = time.time() - start
    try:
        body = b""
        async for chunk in response.body_iterator:
            body += chunk
        new_resp = Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
        logger.info(
            "← Response %s in %.3fs Body=%s",
            new_resp.status_code,
            process_time,
            body.decode("utf-8", errors="replace"),
        )
        return new_resp
    except Exception:
        logger.exception("Error while reading response body")
        return response

app.include_router(router)

@app.on_event("startup")
async def on_startup():
    async with async_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    await database.connect()
    logger.info("Application startup complete")

@app.on_event("shutdown")
async def on_shutdown():
    await database.disconnect()
    logger.info("Application shutdown complete")