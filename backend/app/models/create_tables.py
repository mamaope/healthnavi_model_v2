from app.models.database import Base, engine
from app.models.user import User

# Create all tables
Base.metadata.create_all(bind=engine)
