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
        status TEXT,         -- SENT / DELIVERED / FAILED
        ref INTEGER,
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS outbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT,
        text TEXT,
        status TEXT DEFAULT 'QUEUE',  -- QUEUE / SENT / FAILED
        ts DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    con.commit()
    con.close()

def save_sms(direction, number, text, status="", ref=None):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO sms(direction,number,text,status,ref) VALUES (?,?,?,?,?)",
        (direction, number, text, status, ref)
    )
    con.commit()
    con.close()

def queue_sms(number, text):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO outbox(number,text) VALUES (?,?)",
        (number, text)
    )
    con.commit()
    con.close()

def get_queued_sms():
    con = conn()
    cur = con.cursor()
    rows = cur.execute(
        "SELECT id,number,text FROM outbox WHERE status='QUEUE' ORDER BY id ASC"
    ).fetchall()
    con.close()
    return rows

def mark_outbox(id, status):
    con = conn()
    cur = con.cursor()
    cur.execute(
        "UPDATE outbox SET status=? WHERE id=?",
        (status, id)
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
