import sqlite3
import json
import os
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, send_file

app = Flask(__name__)
app.secret_key = "super_secret_kids_learning_key"
DATABASE = "learning_app.db"

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    # Profiles Table (Kids under a user account)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            avatar TEXT NOT NULL,
            stars INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    # Progress & Analytics Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id INTEGER NOT NULL,
            game_name TEXT NOT NULL,
            item_tested TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (profile_id) REFERENCES profiles (id)
        )
    ''')
    conn.commit()
    conn.close()

# ---------------------------------------------------------
# FLASK BACKEND ROUTES (AUTH, PROFILES, ANALYTICS)
# ---------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required!'})
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
        user_id = cursor.lastrowid
        # Create a default child profile
        cursor.execute('INSERT INTO profiles (user_id, name, avatar, stars) VALUES (?, ?, ?, ?)', 
                       (user_id, 'Little Star', '🦁', 0))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Registration successful! You can now log in.'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username already exists!'})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        return jsonify({'success': True, 'username': user['username']})
    return jsonify({'success': False, 'message': 'Invalid credentials!'})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/session', methods=['GET'])
def get_session():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'username': session['username']})
    return jsonify({'logged_in': False})

@app.route('/api/profiles', methods=['GET', 'POST'])
def handle_profiles():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        name = data.get('name', 'Kiddo')
        avatar = data.get('avatar', '🐶')
        cursor.execute('INSERT INTO profiles (user_id, name, avatar, stars) VALUES (?, ?, ?, ?)',
                       (session['user_id'], name, avatar, 0))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    
    cursor.execute('SELECT * FROM profiles WHERE user_id = ?', (session['user_id'],))
    profiles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(profiles)

@app.route('/api/record_progress', methods=['POST'])
def record_progress():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    profile_id = data.get('profile_id')
    game_name = data.get('game_name')
    item_tested = data.get('item_tested')
    is_correct = 1 if data.get('is_correct') else 0
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Record attempt
    cursor.execute('INSERT INTO progress (profile_id, game_name, item_tested, is_correct) VALUES (?, ?, ?, ?)',
                   (profile_id, game_name, item_tested, is_correct))
    
    # Award Star if correct
    if is_correct:
        cursor.execute('UPDATE profiles SET stars = stars + 1 WHERE id = ?', (profile_id,))
    
    conn.commit()
    cursor.execute('SELECT stars FROM profiles WHERE id = ?', (profile_id,))
    updated_stars = cursor.fetchone()['stars']
    conn.close()
    
    return jsonify({'success': True, 'stars': updated_stars})

@app.route('/api/analytics/<int:profile_id>', methods=['GET'])
def get_analytics(profile_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Mastery per item
    cursor.execute('''
        SELECT item_tested, 
               COUNT(*) as total_attempts,
               SUM(is_correct) as correct_attempts
        FROM progress 
        WHERE profile_id = ?
        GROUP BY item_tested
    ''', (profile_id,))
    
    mastery_data = [dict(row) for row in cursor.fetchall()]
    
    # Total Games Played
    cursor.execute('SELECT COUNT(*) as games_count FROM progress WHERE profile_id = ?', (profile_id,))
    total_played = cursor.fetchone()['games_count']
    
    conn.close()
    return jsonify({
        'total_played': total_played,
        'mastery': mastery_data
    })

@app.route('/download-my-secret-db-xyz')
def download_db():
    # Palitan ang 'database.db' kung ano man ang exact filename/path ng sqlite DB mo
    db_path = 'learning_app.db' 
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True)
    return f"File not found at {os.path.abspath(db_path)}", 404

# ---------------------------------------------------------
# SINGLE-FILE FRONTEND HTML & JS
# ---------------------------------------------------------
@app.route('/')
def index():

    if 'user_id' not in session:
        return render_template('index.html', session=session, auth_error=None)
   
    return render_template('index.html', auth_error=None)

# ---------------------------------------------------------
# APPLICATION ENTRY POINT
# ---------------------------------------------------------
if __name__ == '__main__':
    init_db()
    print("--------------------------------------------------")
    print("🚀 Kids Learning Flask Server Running!")
    print("🌐 Open http://127.0.0.1:5000 in your browser.")
    print("--------------------------------------------------")
    app.run(debug=True)