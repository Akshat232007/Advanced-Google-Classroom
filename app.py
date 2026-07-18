import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models.database import init_db, get_db_connection

app = Flask(__name__)
app.secret_key = 'super_secret_classroom_key'

os.makedirs('uploads', exist_ok=True)
init_db()

# --- HELPER FUNCTIONS ---
def generate_code(prefix="SCH", length=6):
    return f"{prefix}-{''.join(random.choices(string.digits, k=length))}"

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Basic NLP Sentiment Analyzer
def analyze_sentiment(text):
    text_lower = text.lower()
    positive_words = ['good', 'great', 'understand', 'clear', 'excellent', 'easy', 'helpful', 'awesome', 'best', 'well', 'perfect']
    negative_words = ['bad', 'confusing', 'hard', 'difficult', 'missed', 'not clear', "didn't", 'did not', 'poor', 'fast', 'boring', 'lost']
    
    pos_score = sum(1 for w in positive_words if w in text_lower)
    neg_score = sum(1 for w in negative_words if w in text_lower)
    
    if neg_score > pos_score: return 'Negative'
    elif pos_score > neg_score: return 'Positive'
    else: return 'Neutral'

# --- ROUTES ---
@app.route('/')
def index():
    if 'user_id' in session: return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_role'] = user['role']
            session['user_name'] = user['name']
            session['school_id'] = user['school_id']
            return redirect(url_for('dashboard'))
        flash("Invalid email or password!")
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        role = request.form['role']
        parent_phone = request.form.get('parent_phone', '') # Only for students
        
        conn = get_db_connection()
        try:
            if role == 'principal':
                school_name = request.form['school_name']
                school_code = generate_code("SCH")
                cursor = conn.cursor()
                cursor.execute("INSERT INTO schools (name, code) VALUES (?, ?)", (school_name, school_code))
                school_id = cursor.lastrowid
                conn.execute("INSERT INTO users (name, email, password, role, school_id) VALUES (?, ?, ?, ?, ?)",
                             (name, email, password, role, school_id))
                flash(f"School created successfully! Your school code is {school_code}")
            else:
                school_code = request.form['school_code']
                school = conn.execute("SELECT id FROM schools WHERE code = ?", (school_code,)).fetchone()
                if not school:
                    flash("Invalid School Code!")
                    return redirect(url_for('register'))
                conn.execute("INSERT INTO users (name, email, password, role, school_id, parent_phone) VALUES (?, ?, ?, ?, ?, ?)",
                             (name, email, password, role, school['id'], parent_phone))
                flash("Registration successful! Please login.")
            
            conn.commit()
            return redirect(url_for('login'))
        except Exception as e:
            flash("Registration error. The email might already be in use.")
        finally:
            conn.close()
            
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    role = session['user_role']
    user_id = session['user_id']
    school_id = session.get('school_id')
    
    if role == 'teacher':
        classrooms = conn.execute('''
            SELECT DISTINCT c.* FROM classrooms c
            LEFT JOIN class_subjects cs ON c.id = cs.classroom_id
            WHERE c.teacher_id = ? OR cs.teacher_id = ?
        ''', (user_id, user_id)).fetchall()
        conn.close()
        return render_template('dashboard.html', classrooms=classrooms)
        
    elif role == 'student':
        classrooms = conn.execute('''SELECT classrooms.* FROM classrooms 
                                     JOIN enrollments ON classrooms.id = enrollments.classroom_id 
                                     WHERE enrollments.user_id = ?''', (user_id,)).fetchall()
        conn.close()
        return render_template('dashboard.html', classrooms=classrooms)
        
    elif role == 'principal':
        school = conn.execute("SELECT * FROM schools WHERE id = ?", (school_id,)).fetchone()
        t_count = conn.execute("SELECT COUNT(*) FROM users WHERE school_id = ? AND role = 'teacher'", (school_id,)).fetchone()[0]
        s_count = conn.execute("SELECT COUNT(*) FROM users WHERE school_id = ? AND role = 'student'", (school_id,)).fetchone()[0]
        
        all_classes = conn.execute('''
            SELECT c.*, 
                   (SELECT COUNT(DISTINCT user_id) FROM enrollments WHERE classroom_id = c.id) as student_count,
                   (SELECT COUNT(DISTINCT teacher_id) FROM class_subjects WHERE classroom_id = c.id) as teacher_count
            FROM classrooms c
            WHERE c.school_id = ?
        ''', (school_id,)).fetchall()
        
        conn.close()
        return render_template('dashboard.html', school=school, t_count=t_count, s_count=s_count, all_classes=all_classes)
    
    conn.close()
    return render_template('dashboard.html')

# --- PRINCIPAL ADVANCED ANALYTICS ---
@app.route('/analytics')
@login_required
def analytics():
    if session['user_role'] != 'principal': return redirect(url_for('dashboard'))
    conn = get_db_connection()
    school_id = session.get('school_id')

    # 1. Subject Understanding Rating
    subject_ratings = conn.execute('''
        SELECT cs.name as subject_name, u.name as teacher_name, 
               AVG(s.rating) as avg_rating, COUNT(s.id) as total_feedback
        FROM class_subjects cs
        JOIN users u ON cs.teacher_id = u.id
        LEFT JOIN assignments a ON cs.id = a.subject_id
        LEFT JOIN submissions s ON a.id = s.assignment_id
        WHERE u.school_id = ?
        GROUP BY cs.id
        ORDER BY avg_rating DESC
    ''', (school_id,)).fetchall()

    # 2. Absentees per Subject
    absence_stats = conn.execute('''
        SELECT cs.name as subject_name, COUNT(a.id) as total_absences
        FROM attendance a
        JOIN class_subjects cs ON a.subject_id = cs.id
        JOIN classrooms c ON cs.classroom_id = c.id
        WHERE c.school_id = ? AND a.status = 'Absent'
        GROUP BY cs.id
        ORDER BY total_absences DESC
    ''', (school_id,)).fetchall()

    # 3. Sentiment Summary (Separate Pos/Neg comments)
    feedbacks = conn.execute('''
        SELECT s.feedback, s.sentiment, cs.name as subject_name, a.title
        FROM submissions s
        JOIN assignments a ON s.assignment_id = a.id
        JOIN class_subjects cs ON a.subject_id = cs.id
        JOIN classrooms c ON cs.classroom_id = c.id
        WHERE c.school_id = ? AND s.feedback IS NOT NULL
        ORDER BY s.submitted_at DESC
        LIMIT 50
    ''', (school_id,)).fetchall()

    conn.close()
    return render_template('analytics.html', ratings=subject_ratings, absences=absence_stats, feedbacks=feedbacks)

# --- WHATSAPP NOTIFICATION TRIGGER ---
@app.route('/trigger_whatsapp_alerts')
@login_required
def trigger_whatsapp_alerts():
    if session['user_role'] != 'principal': return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    school_id = session.get('school_id')
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Find assignments past deadline
    overdue_assignments = conn.execute('''
        SELECT a.id, a.title, c.name as class_name, cs.name as subject_name 
        FROM assignments a
        JOIN classrooms c ON a.classroom_id = c.id
        JOIN class_subjects cs ON a.subject_id = cs.id
        WHERE c.school_id = ? AND a.deadline < ?
    ''', (school_id, today)).fetchall()

    alerts_sent = 0
    for assign in overdue_assignments:
        # Find students in this class who haven't submitted
        missing_students = conn.execute('''
            SELECT u.name, u.parent_phone 
            FROM users u
            JOIN enrollments e ON u.id = e.user_id
            WHERE e.classroom_id = (SELECT classroom_id FROM assignments WHERE id = ?)
            AND u.role = 'student'
            AND u.id NOT IN (SELECT student_id FROM submissions WHERE assignment_id = ?)
            AND u.parent_phone IS NOT NULL AND u.parent_phone != ''
        ''', (assign['id'], assign['id'])).fetchall()

        for student in missing_students:
            # SIMULATED WHATSAPP MESSAGE
            msg_en = f"Alert: {student['name']} has missed the deadline for the '{assign['subject_name']}' assignment ({assign['title']}). Please ensure it is submitted."
            msg_hi = f"Sandesh: {student['name']} ne '{assign['subject_name']}' ka assignment ({assign['title']}) samay par jama nahi kiya hai. Kripya dhyan dein."
            
            print(f"--- WHATSAPP SENT TO {student['parent_phone']} ---")
            print(msg_en)
            print(msg_hi)
            print("-----------------------------------------")
            alerts_sent += 1

    conn.close()
    flash(f"Successfully sent {alerts_sent} automated WhatsApp alerts to parents regarding pending assignments!")
    return redirect(url_for('dashboard'))


# --- CLASSROOM ROUTES ---
@app.route('/classroom/create', methods=['POST'])
@login_required
def create_classroom():
    if session['user_role'] in ['teacher', 'principal']:
        name = request.form['name']
        subject = request.form.get('subject', 'General')
        code = generate_code(name[:3].upper(), 4)
        conn = get_db_connection()
        conn.execute("INSERT INTO classrooms (name, subject, code, teacher_id, school_id) VALUES (?, ?, ?, ?, ?)",
                     (name, subject, code, session['user_id'], session['school_id']))
        conn.commit()
        conn.close()
        flash("New class created successfully!")
    return redirect(url_for('dashboard'))

@app.route('/classroom/join', methods=['POST'])
@login_required
def join_classroom():
    if session['user_role'] == 'student':
        code = request.form['code'].strip()
        conn = get_db_connection()
        classroom = conn.execute("SELECT id FROM classrooms WHERE code = ? AND school_id = ?", (code, session['school_id'])).fetchone()
        if classroom:
            enrolled = conn.execute("SELECT id FROM enrollments WHERE user_id = ? AND classroom_id = ?", (session['user_id'], classroom['id'])).fetchone()
            if not enrolled:
                conn.execute("INSERT INTO enrollments (user_id, classroom_id) VALUES (?, ?)", (session['user_id'], classroom['id']))
                conn.commit()
                flash("Successfully joined the class!")
            else:
                flash("You are already enrolled in this class.")
        else:
            flash("Invalid class code.")
        conn.close()
    return redirect(url_for('dashboard'))

@app.route('/classroom/<int:id>')
@login_required
def classroom(id):
    conn = get_db_connection()
    cls = conn.execute("SELECT * FROM classrooms WHERE id = ?", (id,)).fetchone()
    subjects = conn.execute('''SELECT cs.*, u.name as teacher_name FROM class_subjects cs JOIN users u ON cs.teacher_id = u.id WHERE cs.classroom_id = ?''', (id,)).fetchall()
    enrolled_students = conn.execute('''SELECT u.id, u.name, u.email FROM users u JOIN enrollments e ON u.id = e.user_id WHERE e.classroom_id = ? AND u.role = 'student' ORDER BY u.name ASC''', (id,)).fetchall()
    school_teachers = []
    if session['user_role'] == 'principal':
        school_teachers = conn.execute("SELECT * FROM users WHERE school_id = ? AND role = 'teacher'", (session['school_id'],)).fetchall()
    conn.close()
    return render_template('classroom.html', classroom=cls, subjects=subjects, enrolled_students=enrolled_students, school_teachers=school_teachers)

@app.route('/classroom/<int:id>/add_subject', methods=['POST'])
@login_required
def add_subject(id):
    if session['user_role'] == 'principal':
        subject_name = request.form['subject_name']
        teacher_id = request.form['teacher_id']
        conn = get_db_connection()
        conn.execute("INSERT INTO class_subjects (classroom_id, name, teacher_id) VALUES (?, ?, ?)", (id, subject_name, teacher_id))
        conn.commit()
        conn.close()
        flash("Subject added and teacher assigned successfully!")
    return redirect(url_for('classroom', id=id))

@app.route('/classroom/<int:id>/assignments')
@login_required
def assignments(id):
    conn = get_db_connection()
    cls = conn.execute("SELECT * FROM classrooms WHERE id = ?", (id,)).fetchone()
    assigns = conn.execute('''SELECT a.*, cs.name as subject_name FROM assignments a LEFT JOIN class_subjects cs ON a.subject_id = cs.id WHERE a.classroom_id = ? ORDER BY a.id DESC''', (id,)).fetchall()
    
    teacher_subjects = []
    if session['user_role'] == 'teacher':
        teacher_subjects = conn.execute('''SELECT * FROM class_subjects WHERE classroom_id = ? AND teacher_id = ?''', (id, session['user_id'])).fetchall()

    student_submissions = {}
    if session['user_role'] == 'student':
        subs = conn.execute("SELECT assignment_id FROM submissions WHERE student_id = ?", (session['user_id'],)).fetchall()
        student_submissions = {s['assignment_id']: True for s in subs}

    conn.close()
    return render_template('assignments.html', classroom=cls, assignments=assigns, teacher_subjects=teacher_subjects, student_submissions=student_submissions)

@app.route('/classroom/<int:id>/assignments/new', methods=['POST'])
@login_required
def new_assignment(id):
    if session['user_role'] == 'teacher':
        title = request.form['title']
        instructions = request.form['instructions']
        deadline = request.form['deadline']
        subject_id = request.form.get('subject_id') 
        conn = get_db_connection()
        conn.execute("INSERT INTO assignments (classroom_id, subject_id, title, instructions, deadline) VALUES (?, ?, ?, ?, ?)",
                     (id, subject_id, title, instructions, deadline))
        conn.commit()
        conn.close()
        flash("Assignment posted successfully!")
    return redirect(url_for('assignments', id=id))

@app.route('/classroom/<int:id>/assignments/<int:aid>/submit', methods=['POST'])
@login_required
def submit_assignment(id, aid):
    if session['user_role'] == 'student':
        content = request.form['content']
        rating = request.form['rating']
        feedback = request.form['feedback']
        
        # Analyze Sentiment automatically
        sentiment = analyze_sentiment(feedback)

        conn = get_db_connection()
        existing = conn.execute("SELECT id FROM submissions WHERE assignment_id = ? AND student_id = ?", (aid, session['user_id'])).fetchone()
        if not existing:
            conn.execute("INSERT INTO submissions (assignment_id, student_id, content, rating, feedback, sentiment) VALUES (?, ?, ?, ?, ?, ?)",
                         (aid, session['user_id'], content, rating, feedback, sentiment))
            conn.commit()
            flash("Assignment turned in successfully!")
        
        conn.close()
    return redirect(url_for('assignments', id=id))

@app.route('/classroom/<int:id>/assignments/<int:aid>/submissions')
@login_required
def view_submissions(id, aid):
    if session['user_role'] not in ['teacher', 'principal']:
        return redirect(url_for('assignments', id=id))
        
    conn = get_db_connection()
    classroom = conn.execute("SELECT * FROM classrooms WHERE id = ?", (id,)).fetchone()
    assignment = conn.execute("SELECT * FROM assignments WHERE id = ?", (aid,)).fetchone()
    
    # Notice: Teachers DO NOT see rating and feedback here. It is excluded from the query/view intentionally.
    submissions = conn.execute('''
        SELECT s.id, s.content, s.status, s.submitted_at, u.name as student_name, u.email as student_email 
        FROM submissions s
        JOIN users u ON s.student_id = u.id
        WHERE s.assignment_id = ?
        ORDER BY s.submitted_at DESC
    ''', (aid,)).fetchall()
    
    conn.close()
    return render_template('submissions.html', classroom=classroom, assignment=assignment, submissions=submissions)

@app.route('/classroom/<int:id>/attendance', methods=['GET', 'POST'])
@login_required
def attendance(id):
    # Same as previous code
    conn = get_db_connection()
    classroom = conn.execute("SELECT * FROM classrooms WHERE id = ?", (id,)).fetchone()

    if request.method == 'POST' and session['user_role'] == 'teacher':
        date = request.form['date']
        subject_id = request.form.get('subject_id')
        conn.execute("DELETE FROM attendance WHERE classroom_id = ? AND subject_id = ? AND date = ?", (id, subject_id, date))
        students = conn.execute('''SELECT users.id FROM users JOIN enrollments ON users.id = enrollments.user_id WHERE enrollments.classroom_id = ?''', (id,)).fetchall()
        for student in students:
            status = 'Present' if request.form.get(f"student_{student['id']}") else 'Absent'
            conn.execute("INSERT INTO attendance (classroom_id, subject_id, student_id, date, status) VALUES (?, ?, ?, ?, ?)", (id, subject_id, student['id'], date, status))
        conn.commit()
        flash(f"Attendance for {date} recorded successfully!")
        
    students = conn.execute('''SELECT users.* FROM users JOIN enrollments ON users.id = enrollments.user_id WHERE enrollments.classroom_id = ?''', (id,)).fetchall()
    teacher_subjects = []
    if session['user_role'] == 'teacher':
        teacher_subjects = conn.execute('''SELECT * FROM class_subjects WHERE classroom_id = ? AND teacher_id = ?''', (id, session['user_id'])).fetchall()

    student_stats = None
    if session['user_role'] == 'student':
        records = conn.execute('''SELECT a.*, cs.name as subject_name FROM attendance a LEFT JOIN class_subjects cs ON a.subject_id = cs.id WHERE a.classroom_id = ? AND a.student_id = ? ORDER BY a.date DESC''', (id, session['user_id'])).fetchall()
        present_count = sum(1 for r in records if r['status'] == 'Present')
        absent_count = sum(1 for r in records if r['status'] == 'Absent')
        total = present_count + absent_count
        percentage = round((present_count / total * 100), 1) if total > 0 else 0
        student_stats = {'total': total, 'present': present_count, 'absent': absent_count, 'percentage': percentage, 'records': records}
    conn.close()
    return render_template('attendance.html', classroom=classroom, students=students, teacher_subjects=teacher_subjects, student_stats=student_stats)

@app.route('/notices', methods=['GET', 'POST'])
@login_required
def notices():
    conn = get_db_connection()
    user_role = session.get('user_role')
    school_id = session.get('school_id')

    if request.method == 'POST' and user_role == 'principal':
        title = request.form['title']
        content = request.form['content']
        audience = request.form.get('audience', 'teacher')
        conn.execute("INSERT INTO notices (school_id, title, content, target_audience) VALUES (?, ?, ?, ?)", (school_id, title, content, audience))
        conn.commit()
        flash("Notice posted successfully!")
        return redirect(url_for('notices'))

    if user_role == 'principal': n = conn.execute("SELECT * FROM notices WHERE school_id = ? ORDER BY id DESC", (school_id,)).fetchall()
    elif user_role == 'teacher': n = conn.execute("SELECT * FROM notices WHERE school_id = ? AND target_audience IN ('teacher', 'all') ORDER BY id DESC", (school_id,)).fetchall()
    else: n = conn.execute("SELECT * FROM notices WHERE school_id = ? AND target_audience IN ('student', 'all') ORDER BY id DESC", (school_id,)).fetchall()

    conn.close()
    return render_template('notices.html', notices=n)

if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True, port=5000)