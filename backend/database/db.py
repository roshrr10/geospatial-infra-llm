from sqlalchemy import create_engine

# Production Database Configuration
DB_USER = "postgres"
DB_PASSWORD = "7654"
DB_HOST = "127.0.0.1"
DB_PORT = "5433"
DB_NAME = "meghalaya_geo_llm"

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# SQLAlchemy engine
engine = create_engine(DATABASE_URL)
