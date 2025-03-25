import os
from pathlib import Path

from loguru import logger
from pydantic import BaseSettings, Field
from dotenv import load_dotenv
import urllib.parse

from labelu.internal.common.io import get_data_dir

# 显式加载.env文件中的环境变量
load_dotenv()
logger.info("Environment variables loaded from .env file")

class Settings(BaseSettings):
    # 基础配置
    SCHEME: str = "http"
    HOST: str = "localhost"
    PORT: str = "8000"
    API_V1_STR: str = "/api/v1"
    MEDIA_HOST: str = f"{SCHEME}://{HOST}:{PORT}"

    # 文件系统配置
    BASE_DATA_DIR: str = get_data_dir()
    MEDIA_ROOT: Path = Path(BASE_DATA_DIR).joinpath("media")
    UPLOAD_DIR: str = "upload"
    EXPORT_DIR: str = "export"
    os.makedirs(MEDIA_ROOT, exist_ok=True)
    logger.info("Database and media directory: {}", BASE_DATA_DIR)
    UPLOAD_FILE_MAX_SIZE: int = 200_000_000  # ~200MB
    THUMBNAIL_HEIGH_PIXEL: int = 120

    # MySQL配置
    MYSQL_HOST: str = Field(default="localhost", env="MYSQL_HOST")
    MYSQL_PORT: str = Field(default="3306", env="MYSQL_PORT")
    MYSQL_USER: str = Field(default="root", env="MYSQL_USER")
    MYSQL_PASSWORD: str = Field(default="", env="MYSQL_PASSWORD")
    MYSQL_DATABASE: str = Field(default="labelu", env="MYSQL_DATABASE")

    # 数据库URL - 优先使用环境变量中的DATABASE_URL，否则使用MySQL配置
    DATABASE_URL: str = Field(
        default=f"sqlite:///{BASE_DATA_DIR}/labelu.sqlite",
        description="Database connection URL. Supports SQLite and MySQL."
    )

    # 安全配置
    PASSWORD_SECRET_KEY: str = (
        "e5b7d00a59aaa2a5ea86a7c4d72f856b20bafa1b8d0e66124082ada81f6340bd"
    )
    TOKEN_GENERATE_ALGORITHM: str = "HS256"
    TOKEN_ACCESS_EXPIRE_MINUTES: int = 30
    TOKEN_TYPE: str = "Bearer"

    def get_mysql_url(self) -> str:
        """Build MySQL URL from individual components"""
        encoded_password = urllib.parse.quote_plus(self.MYSQL_PASSWORD, safe='')
        return f"mysql://{self.MYSQL_USER}:{encoded_password}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def need_migration_to_mysql(self) -> bool:
        """Check if migration to MySQL is needed"""
        sqlite_path = Path(self.BASE_DATA_DIR) / "labelu.sqlite"
        return (
            self.DATABASE_URL.startswith('mysql') and 
            sqlite_path.exists()
        )

    class Config:
        env_prefix = ""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

# 如果没有设置DATABASE_URL，则使用MySQL配置
if os.environ.get("MYSQL_HOST"):
    settings.DATABASE_URL = settings.get_mysql_url()
    logger.info("Using MySQL database: {}", settings.DATABASE_URL)
else:
    logger.info("Using database: {}", settings.DATABASE_URL)
