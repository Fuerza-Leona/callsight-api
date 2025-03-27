from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

router = APIRouter(prefix="/users", tags=["users"]) 