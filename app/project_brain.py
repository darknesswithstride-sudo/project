"""Persistent local project brain: conversation history, project notes, and run summaries."""
from __future__ import annotations
import json, sqlite3, time
from pathlib import Path
from .config import WORKSPACE_DIR
DB = (WORKSPACE_DIR / 'omniforge_brain.sqlite3').resolve()
DB.parent.mkdir(parents=True, exist_ok=True)

def _conn():
    c=sqlite3.connect(DB, timeout=10)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript('''
    CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY, created_at REAL NOT NULL, updated_at REAL NOT NULL, title TEXT NOT NULL DEFAULT 'New conversation');
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS project_memory(id INTEGER PRIMARY KEY AUTOINCREMENT, project_key TEXT NOT NULL, kind TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL, UNIQUE(project_key,kind,content));
    CREATE TABLE IF NOT EXISTS runs(job_id TEXT PRIMARY KEY, session_id TEXT NOT NULL, command TEXT NOT NULL, status TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '', updated_at REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id,id);
    CREATE INDEX IF NOT EXISTS idx_memory_project ON project_memory(project_key,id);
    ''')
    return c

def create_session(session_id: str, title: str='New conversation'):
    now=time.time()
    with _conn() as c: c.execute('INSERT OR IGNORE INTO sessions(session_id,created_at,updated_at,title) VALUES(?,?,?,?)',(session_id,now,now,title[:120]))

def add_message(session_id: str, role: str, content: str):
    now=time.time()
    with _conn() as c:
        c.execute('INSERT OR IGNORE INTO sessions(session_id,created_at,updated_at,title) VALUES(?,?,?,?)',(session_id,now,now,content[:120] if role=='user' else 'New conversation'))
        c.execute('INSERT INTO messages(session_id,role,content,created_at) VALUES(?,?,?,?)',(session_id,role,content[:24000],now))
        c.execute('UPDATE sessions SET updated_at=? WHERE session_id=?',(now,session_id))

def history(session_id: str, limit: int=16):
    with _conn() as c: rows=c.execute('SELECT role,content,created_at FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?', (session_id,max(1,min(40,limit)))).fetchall()
    return [dict(x) for x in reversed(rows)]

def remember(project_key: str, kind: str, content: str):
    content=' '.join(str(content).split())[:3000]
    if not content: return
    with _conn() as c: c.execute('INSERT OR IGNORE INTO project_memory(project_key,kind,content,created_at) VALUES(?,?,?,?)',(project_key[:240],kind[:40],content,time.time()))

def recall(project_key: str='.', limit: int=18):
    with _conn() as c:
        rows=c.execute('SELECT kind,content,created_at FROM project_memory WHERE project_key IN (?, "*") ORDER BY created_at DESC LIMIT ?', (project_key,max(1,min(50,limit)))).fetchall()
    return [dict(x) for x in reversed(rows)]

def save_run(job_id: str, session_id: str, command: str, status: str, summary: str=''):
    with _conn() as c: c.execute('INSERT INTO runs(job_id,session_id,command,status,summary,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(job_id) DO UPDATE SET status=excluded.status,summary=excluded.summary,updated_at=excluded.updated_at',(job_id,session_id,command[:12000],status[:60],summary[:3000],time.time()))

def sessions(limit: int=30):
    with _conn() as c: rows=c.execute('SELECT session_id,created_at,updated_at,title FROM sessions ORDER BY updated_at DESC LIMIT ?', (max(1,min(100,limit)),)).fetchall()
    return [dict(x) for x in rows]
