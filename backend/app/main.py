from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth, clients, sites, sales_preview, prospecting
from .routes import health

app = FastAPI(title="GEO Suite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(clients.router)
app.include_router(sites.router)
app.include_router(sales_preview.router)
app.include_router(prospecting.router)
app.include_router(health.router)
