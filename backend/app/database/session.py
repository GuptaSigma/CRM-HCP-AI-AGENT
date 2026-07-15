import pymysql
from contextlib import contextmanager
from app.core.config import settings

class MySQLConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query, params=None):
        query = query.replace("?", "%s")
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return MySQLCursorWrapper(cursor)

    def executemany(self, query, params=None):
        query = query.replace("?", "%s")
        cursor = self.conn.cursor()
        cursor.executemany(query, params)
        return MySQLCursorWrapper(cursor)

    def executescript(self, script):
        statements = script.split(";")
        cursor = self.conn.cursor()
        for statement in statements:
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt.replace("?", "%s"))
        return MySQLCursorWrapper(cursor)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

class MySQLCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def rowcount(self):
        return self.cursor.rowcount

@contextmanager
def get_connection():
    connection = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password,
        database=settings.mysql_database,
        cursorclass=pymysql.cursors.DictCursor
    )
    wrapper = MySQLConnectionWrapper(connection)
    try:
        yield wrapper
        wrapper.commit()
    except Exception:
        wrapper.rollback()
        raise
    finally:
        wrapper.close()

def initialize_database() -> None:
    # Connect without specifying database to create database if not exists
    conn = pymysql.connect(
        host=settings.mysql_host,
        port=settings.mysql_port,
        user=settings.mysql_user,
        password=settings.mysql_password
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {settings.mysql_database}")
    finally:
        conn.close()

    with get_connection() as conn_wrapper:
        conn_wrapper.executescript(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id VARCHAR(255) PRIMARY KEY,
                hcp_name VARCHAR(255) NOT NULL,
                interaction_type VARCHAR(255) NOT NULL,
                occurred_at VARCHAR(255) NOT NULL,
                attendees TEXT,
                topics_discussed TEXT,
                voice_note_summary TEXT,
                sentiment VARCHAR(50) NOT NULL DEFAULT 'neutral',
                outcomes TEXT,
                created_at VARCHAR(255) NOT NULL,
                updated_at VARCHAR(255) NOT NULL
            );
            CREATE TABLE IF NOT EXISTS materials (
                id VARCHAR(255) PRIMARY KEY,
                interaction_id VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS samples (
                id VARCHAR(255) PRIMARY KEY,
                interaction_id VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                quantity INT NOT NULL DEFAULT 1,
                FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS follow_ups (
                id VARCHAR(255) PRIMARY KEY,
                interaction_id VARCHAR(255) NOT NULL,
                task TEXT NOT NULL,
                due_date VARCHAR(255),
                completed INT NOT NULL DEFAULT 0,
                FOREIGN KEY (interaction_id) REFERENCES interactions(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS hcps (
                id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                specialty VARCHAR(255) NOT NULL,
                organization VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL
            );
            """
        )
        
        # Populate hcps with mock data if table is empty
        cursor = conn_wrapper.execute("SELECT COUNT(*) as count FROM hcps")
        res = cursor.fetchone()
        if res.get('count', 0) == 0:
            mock_hcps = [
                ("1", "Dr. Sarah Jenkins", "Cardiology", "Boston Medical Center", "sarah.jenkins@bmc.org"),
                ("2", "Dr. Anil Sharma", "Oncology", "Apollo Hospital", "anil.sharma@apollo.com"),
                ("3", "Dr. Emily Chen", "Pediatrics", "Children's Hospital", "emily.chen@childrens.org"),
                ("4", "Dr. Marcus Vance", "Neurology", "Neurological Institute", "marcus.vance@neuroinst.org"),
                ("5", "Dr. Sofia Rodriguez", "Endocrinology", "Metro Health", "sofia.rodriguez@metrohealth.org")
            ]
            conn_wrapper.executemany(
                "INSERT INTO hcps (id, name, specialty, organization, email) VALUES (?, ?, ?, ?, ?)",
                mock_hcps
            )
