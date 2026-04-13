import os
from pathlib import Path

import pandas as pd
import psycopg2


DEFAULTS = {
    "host": "localhost",
    "port": "5433",
    "dbname": "Basketball",
    "user": "postgres",
    "password": "",
}


def _load_project_env_file() -> None:
    """
    Load C:/leumit/.env into process env (non-destructive).
    """
    root_env = Path(__file__).resolve().parents[3] / ".env"
    if not root_env.exists():
        return

    for raw in root_env.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_project_env_file()


def _cfg() -> dict[str, str]:
    return {
        "host": os.getenv("DB_HOST", DEFAULTS["host"]),
        "port": os.getenv("DB_PORT", DEFAULTS["port"]),
        "dbname": os.getenv("DB_NAME", DEFAULTS["dbname"]),
        "user": os.getenv("DB_USER", DEFAULTS["user"]),
        "password": os.getenv("DB_PASSWORD", DEFAULTS["password"]),
    }


def validate_db_config_or_raise() -> None:
    c = _cfg()
    missing = []
    if not c["password"]:
        missing.append("DB_PASSWORD")

    if missing:
        raise RuntimeError(
            "Missing required DB configuration: "
            + ", ".join(missing)
            + ". Create C:/leumit/.env with DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD."
        )


def get_conn():
    c = _cfg()
    return psycopg2.connect(
        host=c["host"],
        port=c["port"],
        dbname=c["dbname"],
        user=c["user"],
        password=c["password"],
    )


def run_query(sql: str, params=None) -> pd.DataFrame:
    with get_conn() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def run_exec(sql: str, params=None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def check_connection() -> tuple[bool, str | None]:
    try:
        validate_db_config_or_raise()
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1;")
        return True, None
    except Exception as e:
        return False, str(e)
