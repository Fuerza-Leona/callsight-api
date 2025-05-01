from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import (
    ai,
    audio,
    conversations,
    users,
    auth,
    companies,
    analysis,
    categories,
    topics,
    tickets,
    chatbot,
    insights,
    reports
)


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=True,
)


# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000/docs",
        "http://localhost:3000",
        "https://staging.callsight.tech",
        "https://callsight.tech",
    ],
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "DELETE",
        "OPTIONS",
    ],  # List methods explicitly
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "Access-Control-Allow-Headers",
    ],  # List headers explicitly
)


# Include routers
app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(users.router, prefix=settings.API_V1_STR)
app.include_router(audio.router, prefix=settings.API_V1_STR)
app.include_router(conversations.router, prefix=settings.API_V1_STR)
app.include_router(ai.router, prefix=settings.API_V1_STR)
app.include_router(companies.router, prefix=settings.API_V1_STR)
app.include_router(analysis.router, prefix=settings.API_V1_STR)
app.include_router(categories.router, prefix=settings.API_V1_STR)
app.include_router(topics.router, prefix=settings.API_V1_STR)
app.include_router(tickets.router, prefix=settings.API_V1_STR)
app.include_router(chatbot.router, prefix=settings.API_V1_STR)
app.include_router(insights.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)


@app.get("/")
def root():
    return {"message": "Welcome to the CallSight API!"}
