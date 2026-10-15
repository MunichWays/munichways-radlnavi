"""Local isolated transfer API: no geo database or routing engine required."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.shared_routes import router

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])
app.include_router(router)
