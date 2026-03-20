from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "ORBIT"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "postgresql+asyncpg://orbit:orbit@localhost:5432/orbit"
    database_url_sync: str = "postgresql://orbit:orbit@localhost:5432/orbit"

    github_token: str = ""
    github_webhook_secret: str = ""

    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-northeast-2"

    vultr_api_key: str = ""

    openai_api_key: str = ""

    obsidian_vault_path: str = r"C:\Users\win11\Desktop\ObsidianVault"

    admin_username: str = "admin"
    admin_password: str = "1234"
    secret_key: str = "orbit-secret-change-me-in-production"

    managed_databases: str = '[{"alias":"orbit","url":"postgresql://orbit:orbit@localhost:5432/orbit","description":"ORBIT 관제 허브"}]'
    managed_servers: str = '[{"name":"local-docker","host":"localhost","type":"docker","description":"로컬 Docker 환경"}]'
    deploy_script_path: str = ""

    ssh_key_path: str = ""
    ssh_host: str = ""
    ssh_user: str = "ubuntu"

    def get_managed_dbs(self) -> list[dict]:
        import json
        return json.loads(self.managed_databases)

    def get_managed_servers(self) -> list[dict]:
        import json
        return json.loads(self.managed_servers)

    class Config:
        env_file = ".env"
        env_prefix = "ORBIT_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
