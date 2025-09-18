from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

load_dotenv()

def get_database_url():
	db_user = os.getenv("DB_USER", "postgres")
	db_password = os.getenv("DB_PASSWORD", "password")
	db_host = os.getenv("DB_HOST", "localhost")
	db_port = os.getenv("DB_PORT", "5432")
	db_name = os.getenv("DB_NAME", "healthnavi")
	return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

DATABASE_URL = os.getenv("DATABASE_URL", get_database_url())

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
