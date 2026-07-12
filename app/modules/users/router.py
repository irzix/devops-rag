from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.modules.users.schema import UserCreate, UserResponse
from app.modules.users.service import UsersService, users_service

router = APIRouter()

# Dependency provider to get the service instance (like NestJS Injectable resolution)
def get_users_service() -> UsersService:
    return users_service

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    service: UsersService = Depends(get_users_service)
):
    # Check if username or email already exists
    for existing_user in service.get_all_users():
        if existing_user["email"] == user_in.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        if existing_user["username"] == user_in.username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # model_dump() is equivalent to converting DTO back to a plain dictionary
    return service.create_user(user_in.model_dump())

@router.get("/", response_model=List[UserResponse])
def read_users(
    service: UsersService = Depends(get_users_service)
):
    return service.get_all_users()

@router.get("/{user_id}", response_model=UserResponse)
def read_user(
    user_id: int,
    service: UsersService = Depends(get_users_service)
):
    user = service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
