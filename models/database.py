import sqlite3
import os

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS schools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        code TEXT UNIQUE NOT NULL
    )''')
    
    # ADDED parent_phone for students WhatsApp alerts
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        school_id INTEGER,
        parent_phone TEXT,
        FOREIGN KEY (school_id) REFERENCES schools (id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS classrooms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subject TEXT,
        code TEXT UNIQUE NOT NULL,
        teacher_id INTEGER,
        school_id INTEGER,
        FOREIGN KEY (teacher_id) REFERENCES users (id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS class_subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER,
        name TEXT NOT NULL,
        teacher_id INTEGER,
        FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
        FOREIGN KEY (teacher_id) REFERENCES users (id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        classroom_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (classroom_id) REFERENCES classrooms (id)
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER,
        subject_id INTEGER,
        title TEXT NOT NULL,
        instructions TEXT,
        deadline TEXT,
        FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
        FOREIGN KEY (subject_id) REFERENCES class_subjects (id)
    )''')

    # ADDED rating, feedback, and sentiment for Data Science analysis
    cursor.execute('''CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER,
        student_id INTEGER,
        content TEXT,
        rating INTEGER,
        feedback TEXT,
        sentiment TEXT,
        status TEXT DEFAULT 'Submitted',
        submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assignment_id) REFERENCES assignments (id),
        FOREIGN KEY (student_id) REFERENCES users (id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        classroom_id INTEGER,
        subject_id INTEGER,
        student_id INTEGER,
        date TEXT,
        status TEXT,
        FOREIGN KEY (classroom_id) REFERENCES classrooms (id),
        FOREIGN KEY (subject_id) REFERENCES class_subjects (id),
        FOREIGN KEY (student_id) REFERENCES users (id)
    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS notices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        school_id INTEGER,
        title TEXT,
        content TEXT,
        target_audience TEXT DEFAULT 'all',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (school_id) REFERENCES schools (id)
    )''')

    # Safe upgrades for existing DB
    try: cursor.execute("ALTER TABLE users ADD COLUMN parent_phone TEXT")
    except: pass 
    try: cursor.execute("ALTER TABLE assignments ADD COLUMN subject_id INTEGER")
    except: pass 
    try: cursor.execute("ALTER TABLE attendance ADD COLUMN subject_id INTEGER")
    except: pass 
    try: 
        cursor.execute("ALTER TABLE submissions ADD COLUMN rating INTEGER")
        cursor.execute("ALTER TABLE submissions ADD COLUMN feedback TEXT")
        cursor.execute("ALTER TABLE submissions ADD COLUMN sentiment TEXT")
    except: pass 

    conn.commit()
    conn.close()