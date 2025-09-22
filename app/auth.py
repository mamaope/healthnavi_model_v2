import os
import vertexai
from dotenv import load_dotenv
from google.auth import load_credentials_from_file
import traceback
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.services.db import get_db
from app.models.user import User as UserModel

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

PROJECT_ID = os.getenv("GCP_ID")
PROJECT_LOCATION = os.getenv("GCP_LOCATION")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v2/token")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    full_name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None

class UserInDB(User):
    hashed_password: str

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_user_by_username(db: Session, username: str):
    return db.query(UserModel).filter(UserModel.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    user = get_user_by_username(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user_by_username(db, token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: UserModel = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Role-based authorization dependencies
async def require_admin_role(current_user: UserModel = Depends(get_current_active_user)):
    """Require admin or super_admin role."""
    if current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

async def require_super_admin_role(current_user: UserModel = Depends(get_current_active_user)):
    """Require super_admin role."""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    return current_user

async def require_user_role(current_user: UserModel = Depends(get_current_active_user)):
    """Require any authenticated user role."""
    return current_user

def initialize_vertexai():
    try:
        logger.info(f"Initializing Vertex AI with project: {PROJECT_ID}, location: {PROJECT_LOCATION}")
        
        if SERVICE_ACCOUNT_FILE:
            logger.info(f"Attempting to load credentials from: {SERVICE_ACCOUNT_FILE}")
            
            if os.path.exists(SERVICE_ACCOUNT_FILE):
                logger.info("Service account file exists, loading credentials...")
                credentials, project_id = load_credentials_from_file(SERVICE_ACCOUNT_FILE)
                vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION, credentials=credentials)
                logger.info(f"Successfully loaded credentials from file for project: {project_id}")
            else:
                logger.error(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")
                logger.info("Falling back to application default credentials...")
                vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION)
        else:
            logger.info("No GOOGLE_APPLICATION_CREDENTIALS environment variable set. Using application default credentials.")
            vertexai.init(project=PROJECT_ID, location=PROJECT_LOCATION)
            
        logger.info("Vertex AI initialization completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise

initialize_vertexai()