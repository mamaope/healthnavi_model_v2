from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.services.db import get_db
from app.services.auth import authenticate_user, get_user_by_email
from app.models.user import User
from app.auth import require_admin_role, require_super_admin_role
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta
import os

router = APIRouter(prefix="/auth", tags=["Authentication"])

SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class UserCreate(BaseModel):
    username: str
    full_name: str | None = None
    email: str
    password: str
    role: str = "user"  # Default role

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", status_code=201)
def register(user: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    
    # Validate role and convert to lowercase
    valid_roles = ["user", "admin", "super_admin"]
    user_role = user.role.lower() if user.role else "user"
    if user_role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")
    
    hashed_password = pwd_context.hash(user.password)
    from datetime import datetime
    
    new_user = User(
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        hashed_password=hashed_password,
        is_active=True,
        role=user_role,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {
        "username": new_user.username, 
        "email": new_user.email,
        "role": new_user.role,
        "created_at": new_user.created_at
    }


# Model for login credentials
class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login", response_model=Token)
def login_for_access_token(login: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login.username, login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    expire = datetime.utcnow() + access_token_expires
    to_encode = {"sub": user.username, "exp": expire}
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}

# Admin endpoints
class UserUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None

class UserResponse(BaseModel):
    id: int
    username: str
    full_name: str | None
    email: str
    role: str
    is_active: bool
    created_at: str | None
    updated_at: str | None

@router.get("/users", response_model=list[UserResponse])
def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role)
):
    """Get all users (admin only)."""
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/users/{user_id}", response_model=UserResponse)
def get_user_by_id(
    user_id: int, 
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role)
):
    """Get user by ID (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role)
):
    """Update user (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Validate role if provided and convert to lowercase
    if user_update.role:
        user_update.role = user_update.role.lower()
        if user_update.role not in ["user", "admin", "super_admin"]:
            raise HTTPException(status_code=400, detail="Invalid role")
    
    # Update fields
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(user)
    return user

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_super_admin_role)
):
    """Delete user (super admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deletion
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}

@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin_role)
):
    """Toggle user active status (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent self-deactivation
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    user.is_active = not user.is_active
    user.updated_at = datetime.utcnow().isoformat()
    db.commit()
    db.refresh(user)
    return {"message": f"User {'activated' if user.is_active else 'deactivated'} successfully"}
