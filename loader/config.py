import os
from dataclasses import dataclass

@dataclass
class Config:
    jira_base_url: str
    jira_auth_type: str
    jira_token: str | None
    jira_username: str | None
    jira_password: str | None
    jql: str
    page_size: int
    pg_host: str
    pg_port: int
    pg_db: str
    pg_user: str
    pg_password: str
    etl_scope_name: str
    etl_overlap_min: int
    # NEW: Cloudflare Access
    cf_access_client_id: str | None
    cf_access_client_secret: str | None
    cf_access_jwt: str | None  # optional: bestehendes Browser-/SSO-JWT (Cookie)

def load_config() -> Config:
    return Config(
        jira_base_url=os.getenv("JIRA_BASE_URL", "").rstrip("/"),
        jira_auth_type=os.getenv("JIRA_AUTH_TYPE", "pat"),
        jira_token=os.getenv("JIRA_TOKEN"),
        jira_username=os.getenv("JIRA_USERNAME"),
        jira_password=os.getenv("JIRA_PASSWORD"),
        jql=os.getenv("JIRA_JQL", "order by updated asc"),
        page_size=int(os.getenv("JIRA_PAGE_SIZE", "100")),
        pg_host=os.getenv("PG_HOST", "127.0.0.1"),
        pg_port=int(os.getenv("PG_PORT", "5432")),
        pg_db=os.getenv("PG_DB", "jira_analytics"),
        pg_user=os.getenv("PG_USER", "jira_etl"),
        pg_password=os.getenv("PG_PASSWORD", ""),
        etl_scope_name=os.getenv("ETL_SCOPE_NAME", "issues_default_scope"),
        etl_overlap_min=int(os.getenv("ETL_OVERLAP_MIN", "5")),
        cf_access_client_id=os.getenv("CF_ACCESS_CLIENT_ID"),
        cf_access_client_secret=os.getenv("CF_ACCESS_CLIENT_SECRET"),
        cf_access_jwt=os.getenv("CF_ACCESS_JWT"),
    )
