import os
import pandas as pd
import psycopg2
import streamlit as st


DEFAULTS = {
    "host": "localhost",
    "port": "5433",
    "dbname": "Basketball",
    "user": "postgres",
    "password": "",
}


def _cfg():
    try:
        return {
            "host": st.secrets["DB_HOST"],
            "port": st.secrets["DB_PORT"],
            "dbname": st.secrets["DB_NAME"],
            "user": st.secrets["DB_USER"],
            "password": st.secrets["DB_PASSWORD"],
        }
    except Exception:
        return {
            "host": os.getenv("DB_HOST", DEFAULTS["host"]),
            "port": os.getenv("DB_PORT", DEFAULTS["port"]),
            "dbname": os.getenv("DB_NAME", DEFAULTS["dbname"]),
            "user": os.getenv("DB_USER", DEFAULTS["user"]),
            "password": os.getenv("DB_PASSWORD", DEFAULTS["password"]),
        }


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


def check_connection():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1;")
        return True, None
    except Exception as e:
        return False, str(e)