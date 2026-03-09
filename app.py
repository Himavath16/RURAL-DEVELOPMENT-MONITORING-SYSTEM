from datetime import datetime, timedelta
import os
import sqlite3
from functools import wraps
from flask import Flask, g, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['DATABASE'] = os.path.join(app.root_path, 'rdms.db')

STATUS_OPTIONS = ['Pending', 'In Progress', 'Completed']
DEPARTMENTS = ['Water Supply Department', 'Road Department', 'Electricity Department', 'Sanitation Department']


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            district TEXT,
            village TEXT
        );

        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            village_name TEXT NOT NULL,
            location TEXT NOT NULL,
            issue_type TEXT NOT NULL,
            description TEXT NOT NULL,
            department TEXT NOT NULL,
            before_photo TEXT,
            status TEXT NOT NULL DEFAULT 'Pending',
            district TEXT NOT NULL,
            created_by INTEGER NOT NULL,
            assigned_officer TEXT,
            expected_completion_date TEXT,
            contractor TEXT,
            sanctioned_budget REAL,
            material_cost REAL,
            other_expenditure REAL,
            workers_info TEXT,
            vendors_info TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY(created_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS progress_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            issue_id INTEGER NOT NULL,
            update_text TEXT NOT NULL,
            progress_photo TEXT,
            updated_by INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(issue_id) REFERENCES issues(id),
            FOREIGN KEY(updated_by) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    ''')
    db.commit()

    seeded = db.execute('SELECT COUNT(*) AS c FROM users').fetchone()['c']
    if seeded == 0:
        users = [
            ('village_rep_1', 'password123', 'village', 'District A', 'Village One'),
            ('district_admin_a', 'password123', 'district', 'District A', None),
            ('state_admin', 'password123', 'state', None, None),
        ]
        db.executemany('INSERT INTO users (username,password,role,district,village) VALUES (?,?,?,?,?)', users)
        db.commit()


def login_required(role=None):
    def wrapper(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('You are not authorized to access this portal.', 'error')
                return redirect(url_for('dashboard'))
            return view(*args, **kwargs)
        return wrapped
    return wrapper


def push_notification_for_role(role, message, district=None):
    db = get_db()
    if role == 'district' and district:
        users = db.execute('SELECT id FROM users WHERE role=? AND district=?', (role, district)).fetchall()
    else:
        users = db.execute('SELECT id FROM users WHERE role=?', (role,)).fetchall()
    now = datetime.utcnow().isoformat()
    for user in users:
        db.execute('INSERT INTO notifications (user_id,message,created_at) VALUES (?,?,?)', (user['id'], message, now))
    db.commit()


@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/init-db')
def initialize_database():
    init_db()
    return 'Database initialized and seeded.'


@app.route('/login', methods=['GET', 'POST'])
def login():
    init_db()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = get_db().execute(
            'SELECT * FROM users WHERE username=? AND password=?', (username, password)
        ).fetchone()
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['district'] = user['district']
            session['village'] = user['village']
            return redirect(url_for('dashboard'))
        flash('Invalid username or password', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required()
def dashboard():
    role = session['role']
    if role == 'village':
        return redirect(url_for('village_portal'))
    if role == 'district':
        return redirect(url_for('district_portal'))
    return redirect(url_for('state_portal'))


@app.route('/village', methods=['GET', 'POST'])
@login_required('village')
def village_portal():
    db = get_db()
    if request.method == 'POST':
        now = datetime.utcnow().isoformat()
        db.execute('''
            INSERT INTO issues (
                village_name, location, issue_type, description, department,
                before_photo, status, district, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'Pending', ?, ?, ?)
        ''', (
            request.form['village_name'],
            request.form['location'],
            request.form['issue_type'],
            request.form['description'],
            request.form['department'],
            request.form.get('before_photo', ''),
            session['district'],
            session['user_id'],
            now,
        ))
        db.commit()
        push_notification_for_role(
            'district',
            f"New issue reported from {request.form['village_name']} ({request.form['issue_type']}).",
            district=session['district']
        )
        flash('Issue reported successfully.', 'success')
        return redirect(url_for('village_portal'))

    issues = db.execute(
        'SELECT * FROM issues WHERE created_by=? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()

    updates = db.execute('''
        SELECT pu.*, i.issue_type FROM progress_updates pu
        JOIN issues i ON i.id = pu.issue_id
        WHERE i.created_by=?
        ORDER BY pu.created_at DESC
    ''', (session['user_id'],)).fetchall()

    return render_template('village.html', issues=issues, updates=updates, departments=DEPARTMENTS)


@app.route('/district', methods=['GET', 'POST'])
@login_required('district')
def district_portal():
    db = get_db()
    if request.method == 'POST':
        issue_id = request.form['issue_id']
        action = request.form['action']

        if action == 'verify_assign':
            expected_days = int(request.form['expected_days'])
            expected_date = (datetime.utcnow() + timedelta(days=expected_days)).date().isoformat()
            db.execute('''
                UPDATE issues SET verified=1, assigned_officer=?, expected_completion_date=?,
                status=?, contractor=?, sanctioned_budget=?, material_cost=?, other_expenditure=?,
                workers_info=?, vendors_info=?
                WHERE id=? AND district=?
            ''', (
                request.form['assigned_officer'],
                expected_date,
                request.form['status'],
                request.form.get('contractor'),
                request.form.get('sanctioned_budget') or None,
                request.form.get('material_cost') or None,
                request.form.get('other_expenditure') or None,
                request.form.get('workers_info', ''),
                request.form.get('vendors_info', ''),
                issue_id,
                session['district']
            ))
            db.commit()
            push_notification_for_role('state', f'Issue #{issue_id} assigned in {session["district"]}.')
            flash(f'Issue #{issue_id} verified and assigned.', 'success')

        elif action == 'progress_update':
            db.execute('UPDATE issues SET status=? WHERE id=? AND district=?', (
                request.form['status'], issue_id, session['district']
            ))
            db.execute('''
                INSERT INTO progress_updates (issue_id, update_text, progress_photo, updated_by, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                issue_id,
                request.form['update_text'],
                request.form.get('progress_photo', ''),
                session['user_id'],
                datetime.utcnow().isoformat(),
            ))
            db.commit()
            push_notification_for_role('district', f'Progress update logged for issue #{issue_id}.', district=session['district'])
            push_notification_for_role('state', f'Progress update logged for issue #{issue_id}.')
            flash(f'Progress updated for issue #{issue_id}.', 'success')

        return redirect(url_for('district_portal'))

    issues = db.execute(
        'SELECT * FROM issues WHERE district=? ORDER BY created_at DESC',
        (session['district'],)
    ).fetchall()

    updates = db.execute('''
        SELECT pu.*, u.username FROM progress_updates pu
        JOIN users u ON pu.updated_by = u.id
        JOIN issues i ON pu.issue_id = i.id
        WHERE i.district=?
        ORDER BY pu.created_at DESC
    ''', (session['district'],)).fetchall()

    return render_template('district.html', issues=issues, updates=updates, status_options=STATUS_OPTIONS)


@app.route('/state')
@login_required('state')
def state_portal():
    db = get_db()
    issues = db.execute('SELECT * FROM issues ORDER BY created_at DESC').fetchall()
    updates = db.execute('''
        SELECT pu.*, i.district, i.issue_type FROM progress_updates pu
        JOIN issues i ON pu.issue_id = i.id
        ORDER BY pu.created_at DESC
    ''').fetchall()
    district_stats = db.execute('''
        SELECT district,
               COUNT(*) as total,
               SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed,
               SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END) as pending,
               SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END) as in_progress
        FROM issues
        GROUP BY district
    ''').fetchall()

    return render_template('state.html', issues=issues, updates=updates, district_stats=district_stats)


@app.route('/notifications')
@login_required()
def notifications():
    db = get_db()
    notes = db.execute(
        'SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC',
        (session['user_id'],)
    ).fetchall()
    db.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (session['user_id'],))
    db.commit()
    return render_template('notifications.html', notes=notes)


if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
