"""
Authentication API routes
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import get_settings
from app.models.schemas import Token, LoginRequest, User, UserCreate
from app.services.auth import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_password_hash,
    require_admin
)
from app.services.database import get_database

router = APIRouter(prefix="/auth", tags=["Authentication"])
settings = get_settings()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_database)
):
    """
    Login with username and password, returns JWT token
    """
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user.get("role", "staff"),
            "name": user.get("name", ""),
            "store_ids": user.get("store_ids", [])
        },
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/json", response_model=Token)
async def login_json(
    login_data: LoginRequest,
    db = Depends(get_database)
):
    """
    Login with JSON body (for mobile/web apps)
    """
    user = await authenticate_user(db, login_data.username, login_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": user["username"],
            "role": user.get("role", "staff"),
            "name": user.get("name", ""),
            "store_ids": user.get("store_ids", [])
        },
        expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    Get current user information
    """
    return {
        "username": current_user["username"],
        "name": current_user.get("name", ""),
        "role": current_user.get("role", "staff"),
        "store_ids": current_user.get("store_ids", [])
    }


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    Create a new user (admin only)
    """
    # Check if username already exists
    existing = await db.users.find_one({"username": user_data.username})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    # Create user document
    user_doc = {
        "username": user_data.username,
        "name": user_data.name,
        "password_hash": get_password_hash(user_data.password),
        "role": user_data.role.value,
        "store_ids": user_data.store_ids
    }
    
    result = await db.users.insert_one(user_doc)
    
    return {
        "id": str(result.inserted_id),
        "username": user_data.username,
        "name": user_data.name,
        "role": user_data.role.value
    }


@router.get("/users")
async def list_users(
    db = Depends(get_database),
    current_user: dict = Depends(require_admin)
):
    """
    List all users (admin only)
    """
    users = await db.users.find(
        {},
        {"password_hash": 0}  # Exclude password hash
    ).to_list(length=None)
    
    # Convert ObjectId to string
    for user in users:
        user["id"] = str(user.pop("_id"))
    
    return users
