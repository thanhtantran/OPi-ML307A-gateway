import sqlite3
from config import DB


def conn():
    return sqlite3.connect(DB, check_same_thread=False)


def init_db():
    con = conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS sms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        direction TEXT,      -- IN / OUT
        number TEXT,
        text TEXT,
        status TEXT,         -- SENT / DELIVERED / FAILED / QUEUED
        ref INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        text TEXT,
        status TEXT DEFAULT 'QUEUE',  -- QUEUE / PROCESSING / SENT / FAILED
        error TEXT,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("PRAGMA table_info(outbox)")
    columns = {row[1] for row in cur.fetchall()}
    if "error" not in columns:
        cur.execute("ALTER TABLE outbox ADD COLUMN error TEXT")
    if "updated_at" not in columns:
        cur.execute("ALTER TABLE outbox ADD COLUMN updated_at DATETIME")

    con.commit()
    con.close()


def save_sms(direction, number, text, status="", ref=None):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sms(direction,number,text,status,ref) VALUES (?,?,?,?,?)",
        (direction, number, text, status, ref),
    )
    con.commit()
    con.close()


def queue_sms(number, text):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO outbox(number,text,status,updated_at) VALUES (?,?,'QUEUE',CURRENT_TIMESTAMP)",
        (number.strip(), text.strip()),
    )
    outbox_id = cur.lastrowid
    cur.execute(
        "INSERT INTO sms(direction,number,text,status,ref) VALUES (?,?,?,?,?)",
        ("OUT", number.strip(), text.strip(), "QUEUED", outbox_id),
    )
    con.commit()
    con.close()
    return outbox_id


def get_queued_sms():
    con = conn()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id,number,text FROM outbox WHERE status='QUEUE' ORDER BY id ASC"
    ).fetchall()
    con.close()
    return rows


def mark_outbox(outbox_id, status, error=None):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "UPDATE outbox SET status=?, error=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (status, error, outbox_id),
    )
    cur.execute(
        "UPDATE sms SET status=? WHERE ref=? AND direction='OUT'",
        (status, outbox_id),
    )
    con.commit()
    con.close()


def list_sms(limit=50):
    con = conn()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT * FROM sms ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    con.close()
    return rows


def list_outbox(limit=50):
    con = conn()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id, number, text, status, error, ts, updated_at FROM outbox ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return rows
