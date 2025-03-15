from typing import Generator
import traceback
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
from loguru import logger

from labelu.internal.common.config import settings

# 获取数据库连接配置
engine = None
database_url = settings.DATABASE_URL

logger.info(f"Connecting to database: {database_url}")
if os.environ.get("DATABASE_URL"):
    logger.info("Using DATABASE_URL from environment variable")

try:
    if settings.DATABASE_URL.startswith('mysql'):
        logger.info("Initializing MySQL database connection")
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=3600,
            # Additional MySQL specific configurations
            connect_args={
                'connect_timeout': 30,  # Connection timeout in seconds
            },
            echo=False,  # Set to True for detailed SQL logging (development only)
        )
        logger.info("MySQL database connection initialized successfully")
    else:
        # SQLite configuration
        logger.info("Initializing SQLite database connection")
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            echo=False,  # Set to False for production, True for development
        )
        logger.info("SQLite database connection initialized successfully")
except SQLAlchemyError as e:
    error_message = str(e)
    logger.error(f"Database connection error: {error_message}")
    logger.error(traceback.format_exc())
    # Re-raise to prevent application from starting with a broken DB connection
    raise

SessionLocal = sessionmaker(autocommit=True, autoflush=False, bind=engine)

Base = declarative_base()

# create database tables
def init_tables() -> None:
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error creating database tables: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def get_db() -> Generator:
    db = None
    try:
        db = SessionLocal()
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database session error: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    finally:
        if db is not None:
            db.close()
