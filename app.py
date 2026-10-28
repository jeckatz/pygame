import sqlite3
import json
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for

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

# ---------------------------------------------------------
# SINGLE-FILE FRONTEND HTML & JS
# ---------------------------------------------------------
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kids Early Learning World 🎈🦁✏️👾</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/canvas-confetti@1.6.0/dist/confetti.browser.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&family=Quicksand:wght@600;700&display=swap" rel="stylesheet">
    
    <style>
        body {
            font-family: 'Fredoka', cursive, sans-serif;
            user-select: none;
            touch-action: manipulation;
        }
        .bg-kids-pattern {
            background-color: #fef08a;
            background-image: radial-gradient(#fbbf24 1.5px, transparent 1.5px), radial-gradient(#fbbf24 1.5px, #fef08a 1.5px);
            background-size: 60px 60px;
        }

        /* Continuous Smooth Swaying & Rising Balloon Physics */
        @keyframes floatAndSway {
            0% { transform: translateY(380px) translateX(0px) rotate(0deg); }
            25% { transform: translateY(280px) translateX(18px) rotate(4deg); }
            50% { transform: translateY(180px) translateX(-18px) rotate(-4deg); }
            75% { transform: translateY(80px) translateX(15px) rotate(3deg); }
            100% { transform: translateY(-120px) translateX(0px) rotate(0deg); }
        }
        .balloon-sway {
            animation: floatAndSway var(--float-duration, 8s) linear infinite;
        }

        /* Balloon Wobble on Wrong Click */
        @keyframes balloonWobble {
            0%, 100% { transform: scale(1) rotate(0deg); }
            20% { transform: scale(0.95) rotate(-12deg); }
            40% { transform: scale(1.05) rotate(12deg); }
            60% { transform: scale(0.98) rotate(-6deg); }
            80% { transform: scale(1.02) rotate(6deg); }
        }
        .balloon-shake {
            animation: balloonWobble 0.5s ease-in-out !important;
        }

        /* Monster Animations */
        @keyframes monsterDance {
            0%, 100% { transform: translateY(0) rotate(0deg) scale(1); }
            25% { transform: translateY(-12px) rotate(-8deg) scale(1.05); }
            75% { transform: translateY(-12px) rotate(8deg) scale(1.05); }
        }
        .monster-happy { animation: monsterDance 0.6s ease-in-out 2; }

        @keyframes monsterShake {
            0%, 100% { transform: translateX(0); }
            20%, 60% { transform: translateX(-10px); }
            40%, 80% { transform: translateX(10px); }
        }
        .monster-sad { animation: monsterShake 0.5s ease-in-out; }

        @keyframes floatText {
            0% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(-40px); }
        }
        .feedback-float { animation: floatText 1s ease-out forwards; }

        #traceCanvas { touch-action: none; cursor: crosshair; }
        .food-item { touch-action: none; user-select: none; }

        #systemBanner{
            z-index: 999;
        }
    </style>
</head>
<body class="bg-kids-pattern min-h-screen text-slate-800 flex flex-col justify-between overflow-x-hidden">

    <!-- Dynamic System Banner Toast -->
    <div id="systemBanner" class="fixed top-4 left-1/2 -translate-x-1/2 z-50 transition-all duration-300 transform -translate-y-20 opacity-0 pointer-events-none">
        <div id="systemBannerContent" class="bg-amber-500 text-white font-extrabold px-6 py-3 rounded-2xl shadow-2xl border-4 border-white text-lg flex items-center gap-3">
            <span id="bannerIcon">💡</span>
            <span id="bannerText">Welcome to Learning Fun!</span>
        </div>
    </div>

   

    <!-- HEADER & NAV -->
    <header class="bg-white/90 backdrop-blur-md shadow-lg border-b-4 border-amber-300 sticky top-0 z-40 px-4 py-3">
        <div class="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3">
            <div class="flex items-center gap-3">
                <div class="w-12 h-12 bg-amber-400 rounded-full flex items-center justify-center text-white text-2xl shadow-md transform -rotate-6">🌟</div>
                <div>
                    <h1 class="text-2xl md:text-3xl font-extrabold text-amber-600 tracking-wide">Kids Learning World</h1>
                    <p class="text-xs font-semibold text-slate-500">Interactive Games with Smart Progress</p>
                </div>
            </div>

            <div class="flex items-center gap-3">
                <div id="profileSelectContainer" class="hidden flex items-center gap-2 bg-amber-50 px-3 py-1.5 rounded-2xl border-2 border-amber-300">
                    <span id="activeAvatar" class="text-2xl">🦁</span>
                    <select id="profileDropdown" onchange="changeProfile()" class="bg-transparent font-bold text-amber-800 text-sm focus:outline-none cursor-pointer"></select>
                </div>

                <div class="flex items-center gap-2 bg-amber-100 px-4 py-1.5 rounded-full border-2 border-amber-300 shadow-inner">
                    <span class="text-2xl animate-bounce">⭐</span>
                    <span id="starCount" class="text-xl font-bold text-amber-700">0</span>
                </div>

                <button id="authBtn" onclick="openAuthModal()" class="bg-indigo-500 hover:bg-indigo-600 text-white font-bold px-4 py-1.5 rounded-xl shadow border-b-4 border-indigo-700 text-sm">
                    🔑 Login
                </button>
            </div>
        </div>

        <nav id="appNav" class="max-w-4xl mx-auto mt-3 flex flex-wrap justify-center gap-2">
            <button onclick="switchTab('balloon')" id="tab-balloon" class="tab-btn bg-pink-500 text-white font-bold px-4 py-2 rounded-2xl shadow border-b-4 border-pink-700 hover:brightness-110 text-sm">🎈 Balloon Pop</button>
            <button onclick="switchTab('safari')" id="tab-safari" class="tab-btn bg-emerald-500 text-white font-bold px-4 py-2 rounded-2xl shadow border-b-4 border-emerald-700 hover:brightness-110 text-sm">🦁 Counting Safari</button>
            <button onclick="switchTab('trace')" id="tab-trace" class="tab-btn bg-sky-500 text-white font-bold px-4 py-2 rounded-2xl shadow border-b-4 border-sky-700 hover:brightness-110 text-sm">✏️ Trace & Learn</button>
            <button onclick="switchTab('monster')" id="tab-monster" class="tab-btn bg-purple-500 text-white font-bold px-4 py-2 rounded-2xl shadow border-b-4 border-purple-700 hover:brightness-110 text-sm">👾 Feed Monster</button>
            <button onclick="switchTab('dashboard')" id="tab-dashboard" class="tab-btn bg-amber-500 text-white font-bold px-4 py-2 rounded-2xl shadow border-b-4 border-amber-700 hover:brightness-110 text-sm">📊 Dashboard</button>
        </nav>
    </header>

    <!-- MAIN APP BODY -->
    <main class="max-w-4xl mx-auto w-full px-4 py-6 flex-grow">

        <!-- AUTH MODAL -->
        <div id="authModal" class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 hidden">
            <div class="bg-white rounded-3xl p-8 max-w-md w-full shadow-2xl border-4 border-amber-300 relative">
                <button onclick="closeAuthModal()" class="absolute top-4 right-4 text-slate-400 hover:text-slate-600 text-xl"><i class="fas fa-times"></i></button>
                <div id="loginForm">
                    <h2 class="text-2xl font-extrabold text-amber-600 mb-4 text-center">Welcome Back! 👋</h2>
                    <input id="loginUsername" type="text" placeholder="Username" class="w-full p-3 mb-3 border-2 border-slate-200 rounded-xl focus:border-amber-400 focus:outline-none">
                    <input id="loginPassword" type="password" placeholder="Password" class="w-full p-3 mb-4 border-2 border-slate-200 rounded-xl focus:border-amber-400 focus:outline-none">
                    <button onclick="submitLogin()" class="w-full bg-amber-500 hover:bg-amber-600 text-white font-bold py-3 rounded-xl shadow border-b-4 border-amber-700 mb-3">Log In</button>
                    <p class="text-center text-xs font-semibold text-slate-500">Don't have an account? <a href="#" onclick="toggleAuthMode()" class="text-amber-600 underline">Register here</a></p>
                </div>
                <div id="registerForm" class="hidden">
                    <h2 class="text-2xl font-extrabold text-amber-600 mb-4 text-center">Create Account 🚀</h2>
                    <input id="regUsername" type="text" placeholder="Choose Username" class="w-full p-3 mb-3 border-2 border-slate-200 rounded-xl focus:border-amber-400 focus:outline-none">
                    <input id="regPassword" type="password" placeholder="Choose Password" class="w-full p-3 mb-4 border-2 border-slate-200 rounded-xl focus:border-amber-400 focus:outline-none">
                    <button onclick="submitRegister()" class="w-full bg-emerald-500 hover:bg-emerald-600 text-white font-bold py-3 rounded-xl shadow border-b-4 border-emerald-700 mb-3">Register</button>
                    <p class="text-center text-xs font-semibold text-slate-500">Already registered? <a href="#" onclick="toggleAuthMode()" class="text-amber-600 underline">Log in here</a></p>
                </div>
            </div>
        </div>

        <!-- GAME 1: BALLOON POP PHONICS -->
        <section id="game-balloon" class="game-section bg-white rounded-3xl p-6 shadow-xl border-4 border-pink-300 relative overflow-hidden min-h-[500px] flex flex-col justify-between">
            <div class="flex flex-col sm:flex-row justify-between items-center bg-pink-50 p-4 rounded-2xl border-2 border-pink-200 gap-2">
                <div>
                    <span class="text-xs uppercase tracking-wider font-bold text-pink-500">Balloon Target</span>
                    <h2 class="text-2xl md:text-3xl font-bold text-pink-700">Pop Balloon: <span id="balloonTarget" class="text-4xl font-extrabold text-pink-600 underline">A</span></h2>
                </div>
                <div class="flex items-center gap-3">
                    <label class="text-xs font-bold text-pink-700">Level:</label>
                    <select id="balloonLevelSelect" onchange="initBalloonGame()" class="bg-white border-2 border-pink-300 font-bold text-pink-700 px-3 py-1.5 rounded-xl text-sm focus:outline-none">
                        <option value="1">Lvl 1 (Easy 1-5 / A-E)</option>
                        <option value="2" selected>Lvl 2 (Medium 1-10 / A-J)</option>
                        <option value="3">Lvl 3 (Fast Full Alphabet)</option>
                    </select>
                </div>
            </div>

            <div id="balloonSky" class="relative w-full h-[340px] overflow-hidden my-4 bg-gradient-to-b from-sky-100 to-sky-200 rounded-2xl border-2 border-sky-300">
                <!-- Dynamic Swaying Balloons -->
            </div>

            <div class="flex justify-between items-center z-10">
                <div class="text-sm font-bold text-slate-500">Level Score: <span id="balloonScore" class="text-pink-600 font-extrabold text-lg">0</span> / 5</div>
                <button onclick="speakTarget()" class="bg-pink-500 hover:bg-pink-600 text-white font-bold px-4 py-2 rounded-xl shadow border-b-4 border-pink-700 text-sm">🔊 Repeat Prompt</button>
            </div>
        </section>

        <!-- GAME 2: COUNTING SAFARI -->
        <section id="game-safari" class="game-section hidden bg-white rounded-3xl p-6 shadow-xl border-4 border-emerald-300 min-h-[500px] flex flex-col justify-between">
            <div class="flex flex-col sm:flex-row justify-between items-center bg-emerald-50 p-4 rounded-2xl border-2 border-emerald-200 gap-2">
                <div>
                    <span class="text-xs uppercase tracking-wider font-bold text-emerald-600">Count Animals</span>
                    <h2 class="text-2xl md:text-3xl font-bold text-emerald-800"><span id="safariAnimalName" class="text-emerald-600 underline">How many do you see?</span></h2>
                </div>
                <select id="safariLevelSelect" onchange="initSafariGame()" class="bg-white border-2 border-emerald-300 font-bold text-emerald-700 px-3 py-1.5 rounded-xl text-sm focus:outline-none">
                    <option value="1">Lvl 1 (Count 1-5)</option>
                    <option value="2" selected>Lvl 2 (Count 1-10)</option>
                </select>
            </div>
            <div id="safariDisplay" class="my-4 p-6 min-h-[220px] bg-gradient-to-b from-emerald-100 to-emerald-200 rounded-2xl border-2 border-emerald-300 flex flex-wrap items-center justify-center gap-4 shadow-inner"></div>
            <div id="safariOptions" class="grid grid-cols-2 sm:grid-cols-4 gap-4"></div>
        </section>

        <!-- GAME 3: TRACE & LEARN -->
        <section id="game-trace" class="game-section hidden bg-white rounded-3xl p-6 shadow-xl border-4 border-sky-300 min-h-[500px] flex flex-col items-center justify-between">
            <div class="w-full flex justify-between items-center bg-sky-50 p-4 rounded-2xl border-2 border-sky-200">
                <div>
                    <span class="text-xs uppercase tracking-wider font-bold text-sky-600">Tracing Practice</span>
                    <h2 class="text-2xl font-bold text-sky-800">Trace: <span id="traceCurrentTarget" class="text-sky-600 underline">A</span></h2>
                </div>
                <div class="flex gap-2">
                    <button onclick="setTraceCategory('letters')" id="btn-trace-letters" class="bg-sky-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow">Letters</button>
                    <button onclick="setTraceCategory('numbers')" id="btn-trace-numbers" class="bg-slate-200 text-slate-700 font-bold px-3 py-1.5 rounded-xl text-xs shadow">Numbers</button>
                </div>
            </div>

            <div class="relative my-4 flex justify-center">
                <canvas id="traceCanvas" width="280" height="280" class="bg-slate-50 border-4 border-dashed border-sky-300 rounded-3xl shadow-inner"></canvas>
            </div>

            <div class="flex gap-4 w-full justify-center">
                <button onclick="clearTraceCanvas()" class="bg-amber-400 hover:bg-amber-500 text-amber-900 font-bold px-5 py-2.5 rounded-xl shadow border-b-4 border-amber-600 text-sm">🧹 Clear Stroke</button>
                <button onclick="evaluateTracingAccuracy()" class="bg-emerald-500 hover:bg-emerald-600 text-white font-bold px-6 py-2.5 rounded-xl shadow border-b-4 border-emerald-700 text-sm">✅ Check Trace</button>
            </div>
        </section>

        <!-- GAME 4: FEED THE HUNGRY MONSTER -->
        <section id="game-monster" class="game-section hidden bg-white rounded-3xl p-6 shadow-xl border-4 border-purple-300 min-h-[500px] flex flex-col justify-between">
            <div class="flex flex-col sm:flex-row justify-between items-center bg-purple-50 p-4 rounded-2xl border-2 border-purple-200 gap-2">
                <div>
                    <span class="text-xs uppercase tracking-wider font-bold text-purple-600">Hungry Monster</span>
                    <h2 class="text-2xl md:text-3xl font-bold text-purple-800">Feed Me: <span id="monsterTarget" class="text-4xl font-extrabold text-purple-600 underline">B</span></h2>
                </div>
                <select id="monsterLevelSelect" onchange="initMonsterGame()" class="bg-white border-2 border-purple-300 font-bold text-purple-700 px-3 py-1.5 rounded-xl text-sm focus:outline-none">
                    <option value="1">Lvl 1 (Letters A-E)</option>
                    <option value="2" selected>Lvl 2 (Match Upper to Lower)</option>
                </select>
            </div>

            <div class="flex flex-col items-center justify-center my-2">
                <div id="monsterDropZone" class="w-48 h-48 bg-purple-100 border-4 border-dashed border-purple-400 rounded-full flex flex-col items-center justify-center p-4 relative transition-all">
                    <svg id="monsterSvg" class="w-36 h-36 transition-transform" viewBox="0 0 100 100">
                        <circle cx="50" cy="50" r="45" fill="#a855f7" />
                        <circle cx="35" cy="35" r="10" fill="white" /><circle id="leftPupil" cx="35" cy="35" r="4" fill="black" />
                        <circle cx="65" cy="35" r="10" fill="white" /><circle id="rightPupil" cx="65" cy="35" r="4" fill="black" />
                        <ellipse id="monsterMouth" cx="50" cy="65" rx="18" ry="10" fill="#4c1d95" class="transition-all duration-200" />
                        <polygon points="40,55 45,62 50,55" fill="white" />
                        <polygon points="50,55 55,62 60,55" fill="white" />
                    </svg>
                    <span class="text-xs font-bold text-purple-600 mt-1">Drag or Click Food Below!</span>
                </div>
            </div>

            <div id="foodItemsContainer" class="flex flex-wrap justify-center gap-4 p-4 bg-purple-50 rounded-2xl border-2 border-purple-200"></div>
        </section>

        <!-- DASHBOARD & PROGRESS TRACKER -->
        <section id="game-dashboard" class="game-section hidden bg-white rounded-3xl p-6 shadow-xl border-4 border-amber-300 min-h-[500px]">
            <div class="text-center bg-amber-50 p-4 rounded-2xl border-2 border-amber-200 mb-6">
                <h2 class="text-2xl font-bold text-amber-800">Learning Dashboard & Mastery 📈</h2>
                <p class="text-xs text-slate-500 font-semibold">Track Progress across all 4 learning games</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="bg-amber-100/50 p-5 rounded-2xl border border-amber-200">
                    <h3 class="font-bold text-amber-900 mb-3 text-lg">Kid Stats</h3>
                    <div class="space-y-3">
                        <div class="flex justify-between items-center bg-white p-3 rounded-xl shadow-sm">
                            <span class="font-bold text-slate-600">Games Attempted:</span>
                            <span id="totalPlayedStat" class="font-extrabold text-amber-600 text-xl">0</span>
                        </div>
                        <div class="flex justify-between items-center bg-white p-3 rounded-xl shadow-sm">
                            <span class="font-bold text-slate-600">Total Stars Earned:</span>
                            <span id="totalStarsStat" class="font-extrabold text-amber-500 text-xl">⭐ 0</span>
                        </div>
                    </div>
                </div>

                <div class="bg-sky-50 p-5 rounded-2xl border border-sky-200">
                    <h3 class="font-bold text-sky-900 mb-3 text-lg">Add Child Profile</h3>
                    <div class="flex gap-2">
                        <input id="newProfileName" type="text" placeholder="Child Name" class="flex-grow p-2.5 rounded-xl border-2 border-sky-200 focus:outline-none text-sm">
                        <select id="newProfileAvatar" class="p-2.5 rounded-xl border-2 border-sky-200 bg-white text-lg">
                            <option value="🦁">🦁</option><option value="🐶">🐶</option><option value="🦄">🦄</option><option value="🐼">🐼</option>
                        </select>
                        <button onclick="addProfile()" class="bg-sky-500 hover:bg-sky-600 text-white font-bold px-4 rounded-xl text-sm shadow">Add</button>
                    </div>
                </div>
            </div>

            <div class="mt-6">
                <h3 class="font-bold text-slate-700 mb-3 text-lg">Mastery Logs</h3>
                <div id="masteryHeatmap" class="grid grid-cols-3 sm:grid-cols-6 gap-3"></div>
            </div>
        </section>

    </main>

    <footer class="text-center py-4 text-xs font-bold text-slate-500 bg-white/60 border-t border-amber-200">
        Flask Python Backend Integration | SQLite Powered Early Learning App
    </footer>

    <script>
        // Global App & Audio State
        let currentProfile = null;
        let profiles = [];
        let loggedIn = false;
        let activeTab = 'balloon';

        // Web Audio Synthesizer
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        let audioCtx = null;

        function playSound(type) {
            if (!audioCtx) audioCtx = new AudioCtx();
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.connect(gain); gain.connect(audioCtx.destination);
            const now = audioCtx.currentTime;

            if (type === 'pop') {
                osc.type = 'sine'; osc.frequency.setValueAtTime(400, now);
                osc.frequency.exponentialRampToValueAtTime(800, now + 0.1);
                gain.gain.setValueAtTime(0.3, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.1);
                osc.start(now); osc.stop(now + 0.1);
            } else if (type === 'wrong') {
                osc.type = 'sawtooth'; osc.frequency.setValueAtTime(180, now);
                osc.frequency.linearRampToValueAtTime(110, now + 0.25);
                gain.gain.setValueAtTime(0.25, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.25);
                osc.start(now); osc.stop(now + 0.25);
            } else if (type === 'eat') {
                osc.type = 'triangle'; osc.frequency.setValueAtTime(280, now);
                osc.frequency.linearRampToValueAtTime(140, now + 0.15);
                gain.gain.setValueAtTime(0.3, now); gain.gain.linearRampToValueAtTime(0.01, now + 0.15);
                osc.start(now); osc.stop(now + 0.15);
            }
        }

        function speak(text) {
            if ('speechSynthesis' in window) {
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(text);
                u.pitch = 1.2; u.rate = 0.9;
                window.speechSynthesis.speak(u);
            }
        }

        function showBanner(message, type = 'info') {
            const banner = document.getElementById('systemBanner');
            const icon = document.getElementById('bannerIcon');
            const text = document.getElementById('bannerText');

            text.innerText = message;
            icon.innerText = type === 'success' ? '🎉' : type === 'error' ? '⚠️' : '💡';

            banner.classList.remove('translate-y-20', 'opacity-0');
            banner.classList.add('translate-y-0', 'opacity-100');

            setTimeout(() => {
                banner.classList.remove('translate-y-0', 'opacity-100');
                banner.classList.add('-translate-y-20', 'opacity-0');
            }, 2500);
        }

        window.onload = async () => {
            await checkSession();
            switchTab('balloon');
        };

        // AUTH & PROFILES
        async function checkSession() {
            const res = await fetch('/api/session');
            const data = await res.json();
            loggedIn = data.logged_in;
            const authBtn = document.getElementById('authBtn');
            if (loggedIn) {
                authBtn.innerText = '🚪 Logout (' + data.username + ')';
                authBtn.onclick = logout;
                document.getElementById('profileSelectContainer').classList.remove('hidden');
                await loadProfiles();
            } else {
                authBtn.innerText = '🔑 Login';
                authBtn.onclick = openAuthModal;
                document.getElementById('profileSelectContainer').classList.add('hidden');
            }
        }

        function openAuthModal() { document.getElementById('authModal').classList.remove('hidden'); }
        function closeAuthModal() { document.getElementById('authModal').classList.add('hidden'); }
        function toggleAuthMode() {
            document.getElementById('loginForm').classList.toggle('hidden');
            document.getElementById('registerForm').classList.toggle('hidden');
        }

        async function submitLogin() {
            const u = document.getElementById('loginUsername').value;
            const p = document.getElementById('loginPassword').value;
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: u, password: p})
            });
            const data = await res.json();
            if (data.success) {
                closeAuthModal();
                await checkSession();
            } else {
                showBanner(data.message, 'error');
            }
        }

        async function submitRegister() {
            const u = document.getElementById('regUsername').value;
            const p = document.getElementById('regPassword').value;
            const res = await fetch('/api/register', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({username: u, password: p})
            });
            const data = await res.json();
            showBanner(data.message, data.success ? 'success' : 'error');
            if (data.success) toggleAuthMode();
        }

        async function logout() {
            await fetch('/api/logout', {method: 'POST'});
            await checkSession();
        }

        async function loadProfiles() {
            const res = await fetch('/api/profiles');
            profiles = await res.json();
            const dropdown = document.getElementById('profileDropdown');
            dropdown.innerHTML = '';
            profiles.forEach(p => {
                const opt = document.createElement('option');
                opt.value = p.id; opt.innerText = p.name;
                dropdown.appendChild(opt);
            });
            if (profiles.length > 0) {
                currentProfile = profiles[0];
                updateProfileUI();
            }
        }

        function changeProfile() {
            const id = parseInt(document.getElementById('profileDropdown').value);
            currentProfile = profiles.find(p => p.id === id);
            updateProfileUI();
        }

        function updateProfileUI() {
            if (currentProfile) {
                document.getElementById('activeAvatar').innerText = currentProfile.avatar;
                document.getElementById('starCount').innerText = currentProfile.stars;
                document.getElementById('totalStarsStat').innerText = '⭐ ' + currentProfile.stars;
            }
        }

        async function addProfile() {
            const name = document.getElementById('newProfileName').value;
            const avatar = document.getElementById('newProfileAvatar').value;
            if (!name) return;
            await fetch('/api/profiles', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({name, avatar})
            });
            document.getElementById('newProfileName').value = '';
            await loadProfiles();
        }

        async function recordProgress(gameName, itemTested, isCorrect) {
            if (!loggedIn || !currentProfile) return;
            const res = await fetch('/api/record_progress', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    profile_id: currentProfile.id,
                    game_name: gameName,
                    item_tested: itemTested,
                    is_correct: isCorrect
                })
            });
            const data = await res.json();
            if (data.success) {
                currentProfile.stars = data.stars;
                updateProfileUI();
                if (isCorrect) confetti({ particleCount: 30, spread: 50, origin: { y: 0.7 } });
            }
        }

        function switchTab(tabName) {
            activeTab = tabName;
            document.querySelectorAll('.game-section').forEach(s => s.classList.add('hidden'));
            document.getElementById(`game-${tabName}`).classList.remove('hidden');

            if (tabName === 'balloon') initBalloonGame();
            if (tabName === 'safari') initSafariGame();
            if (tabName === 'trace') initTraceGame();
            if (tabName === 'monster') initMonsterGame();
            if (tabName === 'dashboard') loadAnalytics();
        }

        /* ---------------------------------------------------
           UPGRADED GAME 1: BALLOON POP (CONTINUOUS ANIMATION)
        --------------------------------------------------- */
        let currentBalloonTarget = '';
        let balloonScore = 0;
        const balloonSets = {
            1: ['A', 'B', 'C', 'D', 'E', '1', '2', '3', '4', '5'],
            2: ['F', 'G', 'H', 'I', 'J', '6', '7', '8', '9', '10'],
            3: ['A','B','C','D','E','F','G','H','I','J','K','L','M','N','O','P','Q','R','S','T','U','V','W','X','Y','Z']
        };

        function initBalloonGame() {
            const sky = document.getElementById('balloonSky');
            sky.innerHTML = '';
            balloonScore = 0;
            document.getElementById('balloonScore').innerText = balloonScore;

            const lvl = document.getElementById('balloonLevelSelect').value;
            const chars = balloonSets[lvl];
            currentBalloonTarget = chars[Math.floor(Math.random() * chars.length)];
            document.getElementById('balloonTarget').innerText = currentBalloonTarget;
            speakTarget();

            // Spawn initial 5 balloons with string (sinulid)
            for (let i = 0; i < 5; i++) {
                spawnSingleBalloon(i);
            }
        }

        function speakTarget() {
            speak(`Pop the balloon with ${currentBalloonTarget}`);
        }

        function spawnSingleBalloon(index) {
            const sky = document.getElementById('balloonSky');
            const lvl = document.getElementById('balloonLevelSelect').value;
            const chars = balloonSets[lvl];
            
            // Check existing letters on screen to ensure target balloon is present
            const existingBalloons = Array.from(sky.querySelectorAll('.balloon-char-text')).map(el => el.innerText);
            let char;
            if (!existingBalloons.includes(currentBalloonTarget)) {
                char = currentBalloonTarget;
            } else {
                char = chars[Math.floor(Math.random() * chars.length)];
            }

            const wrapper = document.createElement('div');
            const colors = ['bg-red-400', 'bg-pink-400', 'bg-purple-400', 'bg-blue-400', 'bg-emerald-400', 'bg-amber-400'];
            const randomColor = colors[Math.floor(Math.random() * colors.length)];
            const randomLeft = 5 + (index * 18) + (Math.random() * 5);
            const duration = lvl == 3 ? (4 + Math.random() * 2) : (7 + Math.random() * 3);

            wrapper.className = `absolute bottom-0 flex flex-col items-center balloon-sway cursor-pointer z-10`;
            wrapper.style.left = `${randomLeft}%`;
            wrapper.style.setProperty('--float-duration', `${duration}s`);

            // Oval Body
            const balloon = document.createElement('div');
            balloon.className = `w-16 h-20 md:w-20 md:h-24 ${randomColor} rounded-full shadow-lg flex items-center justify-center text-white text-2xl font-bold border-b-4 border-black/20 relative`;
            
            const charSpan = document.createElement('span');
            charSpan.className = 'balloon-char-text';
            charSpan.innerText = char;
            balloon.appendChild(charSpan);

            // Knot
            const knot = document.createElement('div');
            knot.className = 'absolute -bottom-1.5 w-3 h-3 bg-inherit rotate-45 rounded-sm';
            balloon.appendChild(knot);

            // Balloon String (Sinulid)
            const stringSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            stringSvg.setAttribute("width", "20");
            stringSvg.setAttribute("height", "45");
            stringSvg.setAttribute("viewBox", "0 0 20 45");
            stringSvg.className = "overflow-visible pointer-events-none mt-1";
            stringSvg.innerHTML = `<path d="M 10,0 Q 20,15 10,30 T 10,45" fill="none" stroke="#64748b" stroke-width="2.5" stroke-linecap="round" />`;

            wrapper.appendChild(balloon);
            wrapper.appendChild(stringSvg);

            wrapper.onclick = (e) => handleBalloonClick(wrapper, e);
            sky.appendChild(wrapper);
        }

        function handleBalloonClick(wrapperElement, e) {
            const charSpan = wrapperElement.querySelector('.balloon-char-text');
            if (!charSpan) return;
            const char = charSpan.innerText;

            if (char === currentBalloonTarget) {
                playSound('pop');
                recordProgress('Balloon Pop', currentBalloonTarget, true);
                
                // POP and remove ONLY the clicked correct balloon
                wrapperElement.remove();
                
                balloonScore += 1;
                document.getElementById('balloonScore').innerText = balloonScore;

                if (balloonScore >= 5) {
                    showBanner("Level Cleared! Awesome Balloon Popping! 🎉", 'success');
                    setTimeout(() => initBalloonGame(), 1200);
                } else {
                    // Advance target letter without re-creating all balloons!
                    const lvl = document.getElementById('balloonLevelSelect').value;
                    const chars = balloonSets[lvl];
                    currentBalloonTarget = chars[Math.floor(Math.random() * chars.length)];
                    document.getElementById('balloonTarget').innerText = currentBalloonTarget;
                    speakTarget();

                    // Spawn a replacement balloon to keep sky full
                    spawnSingleBalloon(Math.floor(Math.random() * 4));

                    // Update remaining balloons seamlessly if needed
                    const sky = document.getElementById('balloonSky');
                    const remainingBalloons = Array.from(sky.querySelectorAll('.balloon-char-text')).map(el => el.innerText);
                    if (!remainingBalloons.includes(currentBalloonTarget)) {
                        const allSpans = sky.querySelectorAll('.balloon-char-text');
                        if (allSpans.length > 0) {
                            const randomSpan = allSpans[Math.floor(Math.random() * allSpans.length)];
                            randomSpan.innerText = currentBalloonTarget;
                        }
                    }
                }
            } else {
                // DO NOT STOP ANIMATION! Shake/wobble in place while floating continues
                playSound('wrong');
                recordProgress('Balloon Pop', currentBalloonTarget, false);
                
                wrapperElement.classList.add('balloon-shake');
                setTimeout(() => wrapperElement.classList.remove('balloon-shake'), 500);

                // Floating Visual Feedback (-1)
                const feedback = document.createElement('div');
                feedback.className = 'absolute text-red-600 font-extrabold text-2xl feedback-float pointer-events-none z-30';
                feedback.style.left = `${e.clientX - 20}px`;
                feedback.style.top = `${e.clientY - 40}px`;
                feedback.innerText = '❌';
                document.body.appendChild(feedback);
                setTimeout(() => feedback.remove(), 1000);

                showBanner(`Oops! That's ${char}. Find ${currentBalloonTarget}!`, 'error');
            }
        }

        /* ---------------------------------------------------
           UPGRADED GAME 2: COUNTING SAFARI
        --------------------------------------------------- */
        let currentSafariCount = 0;
        function initSafariGame() {
            const display = document.getElementById('safariDisplay');
            const options = document.getElementById('safariOptions');
            display.innerHTML = ''; options.innerHTML = '';

            const lvl = document.getElementById('safariLevelSelect').value;
            const max = lvl == 1 ? 5 : 10;
            currentSafariCount = Math.floor(Math.random() * max) + 1;

            speak(`How many do you see?`);

            for (let i = 0; i < currentSafariCount; i++) {
                const el = document.createElement('div');
                el.className = 'text-5xl animate-bounce cursor-pointer transition transform hover:scale-125';
                el.innerText = '🐵';
                el.onclick = () => playSound('pop');
                display.appendChild(el);
            }

            let choices = [currentSafariCount];
            while (choices.length < 4) {
                let r = Math.floor(Math.random() * max) + 1;
                if (!choices.includes(r)) choices.push(r);
            }
            choices.sort(() => Math.random() - 0.5);

            choices.forEach(num => {
                const btn = document.createElement('button');
                btn.className = 'bg-emerald-500 hover:bg-emerald-600 text-white font-extrabold text-3xl py-3 rounded-2xl shadow-lg border-b-4 border-emerald-700';
                btn.innerText = num;
                btn.onclick = () => {
                    const isCorrect = num === currentSafariCount;
                    recordProgress('Counting Safari', String(currentSafariCount), isCorrect);
                    if (isCorrect) {
                        showBanner("Great counting!", 'success');
                        setTimeout(initSafariGame, 1000);
                    } else {
                        playSound('wrong');
                        showBanner("Try counting again!", 'error');
                    }
                };
                options.appendChild(btn);
            });
        }

        /* ---------------------------------------------------
           UPGRADED GAME 3: TRACE & LEARN (GENTLE ACCURACY)
        --------------------------------------------------- */
        let traceCategory = 'letters';
        let traceIndex = 0;
        const traceLetters = ['A', 'B', 'C', 'D', 'E'];
        const traceNumbers = ['1', '2', '3', '4', '5'];
        let traceCanvas, traceCtx, isTracing = false;
        let maskCanvas, maskCtx;

        function initTraceGame() {
            traceCanvas = document.getElementById('traceCanvas');
            traceCtx = traceCanvas.getContext('2d');
            
            maskCanvas = document.createElement('canvas');
            maskCanvas.width = traceCanvas.width;
            maskCanvas.height = traceCanvas.height;
            maskCtx = maskCanvas.getContext('2d');

            traceCanvas.onmousedown = startTrace;
            traceCanvas.onmousemove = drawTrace;
            traceCanvas.onmouseup = stopTrace;

            traceCanvas.ontouchstart = (e) => { e.preventDefault(); startTrace(e.touches[0]); };
            traceCanvas.ontouchmove = (e) => { e.preventDefault(); drawTrace(e.touches[0]); };
            traceCanvas.ontouchend = stopTrace;

            clearTraceCanvas();
        }

        function setTraceCategory(cat) {
            traceCategory = cat;
            traceIndex = 0;
            document.getElementById('btn-trace-letters').className = cat === 'letters' ? 'bg-sky-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow' : 'bg-slate-200 text-slate-700 font-bold px-3 py-1.5 rounded-xl text-xs shadow';
            document.getElementById('btn-trace-numbers').className = cat === 'numbers' ? 'bg-sky-500 text-white font-bold px-3 py-1.5 rounded-xl text-xs shadow' : 'bg-slate-200 text-slate-700 font-bold px-3 py-1.5 rounded-xl text-xs shadow';
            clearTraceCanvas();
        }

        function clearTraceCanvas() {
            const currentList = traceCategory === 'letters' ? traceLetters : traceNumbers;
            const char = currentList[traceIndex];
            document.getElementById('traceCurrentTarget').innerText = char;

            traceCtx.clearRect(0, 0, traceCanvas.width, traceCanvas.height);
            traceCtx.font = 'bold 170px Fredoka, sans-serif';
            traceCtx.fillStyle = '#cbd5e1';
            traceCtx.textAlign = 'center';
            traceCtx.textBaseline = 'middle';
            traceCtx.fillText(char, traceCanvas.width / 2, traceCanvas.height / 2 + 10);

            maskCtx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
            maskCtx.font = 'bold 170px Fredoka, sans-serif';
            maskCtx.fillStyle = '#000000';
            maskCtx.textAlign = 'center';
            maskCtx.textBaseline = 'middle';
            maskCtx.fillText(char, maskCanvas.width / 2, maskCanvas.height / 2 + 10);

            speak(`Trace ${char}`);
        }

        function startTrace(e) {
            isTracing = true;
            drawTrace(e);
        }

        function drawTrace(e) {
            if (!isTracing) return;
            const rect = traceCanvas.getBoundingClientRect();
            const x = (e.clientX || e.pageX) - rect.left;
            const y = (e.clientY || e.pageY) - rect.top;

            traceCtx.fillStyle = '#0284c7';
            traceCtx.beginPath();
            traceCtx.arc(x, y, 12, 0, Math.PI * 2);
            traceCtx.fill();
        }

        function stopTrace() { isTracing = false; }

        function evaluateTracingAccuracy() {
            const currentList = traceCategory === 'letters' ? traceLetters : traceNumbers;
            const char = currentList[traceIndex];

            const maskImgData = maskCtx.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
            const userImgData = traceCtx.getImageData(0, 0, traceCanvas.width, traceCanvas.height).data;

            let totalTargetPixels = 0;
            let coveredTargetPixels = 0;

            for (let i = 0; i < maskImgData.length; i += 4) {
                const isMaskPixel = maskImgData[i + 3] > 100;
                const isDrawnPixel = (userImgData[i] === 2 && userImgData[i + 1] === 132 && userImgData[i + 2] === 199);

                if (isMaskPixel) {
                    totalTargetPixels++;
                    if (isDrawnPixel) coveredTargetPixels++;
                }
            }

            const coverageRatio = totalTargetPixels > 0 ? (coveredTargetPixels / totalTargetPixels) : 0;

            if (coverageRatio >= 0.25) {
                recordProgress('Trace & Learn', char, true);
                showBanner(`Wonderful Tracing of ${char}! 🎨`, 'success');

                traceIndex = (traceIndex + 1) % currentList.length;
                setTimeout(clearTraceCanvas, 1200);
            } else {
                playSound('wrong');
                recordProgress('Trace & Learn', char, false);
                showBanner("Draw over the letter lines to finish! ✏️", 'error');
            }
        }

        /* ---------------------------------------------------
           UPGRADED GAME 4: FEED THE MONSTER (FULL TOUCH & DRAG)
        --------------------------------------------------- */
        let currentMonsterTarget = '';
        function initMonsterGame() {
            const container = document.getElementById('foodItemsContainer');
            container.innerHTML = '';

            const lvl = document.getElementById('monsterLevelSelect').value;
            const targets = ['A', 'B', 'C', 'D', 'E'];
            
            currentMonsterTarget = targets[Math.floor(Math.random() * targets.length)];
            document.getElementById('monsterTarget').innerText = currentMonsterTarget;

            speak(`Feed the monster target ${currentMonsterTarget}`);

            let choices = lvl == 1 ? ['A', 'B', 'C', 'D', 'E'] : ['a', 'b', 'c', 'd', 'e'];
            choices.sort(() => Math.random() - 0.5);

            choices.forEach(item => {
                const food = document.createElement('div');
                food.className = 'food-item w-16 h-16 bg-purple-200 border-4 border-purple-400 rounded-2xl flex items-center justify-center font-extrabold text-2xl text-purple-900 cursor-grab active:cursor-grabbing shadow-md transition transform hover:scale-110';
                food.innerText = item;
                food.setAttribute('draggable', 'true');

                food.ondragstart = (e) => {
                    e.dataTransfer.setData('text/plain', item);
                    document.getElementById('monsterMouth').setAttribute('ry', '18');
                };
                food.ondragend = () => {
                    document.getElementById('monsterMouth').setAttribute('ry', '10');
                };

                setupTouchDrag(food, item);
                food.onclick = () => handleFeedMonster(item);
                container.appendChild(food);
            });

            const dropZone = document.getElementById('monsterDropZone');
            dropZone.ondragover = (e) => {
                e.preventDefault();
                document.getElementById('monsterMouth').setAttribute('ry', '22');
            };
            dropZone.ondragleave = () => {
                document.getElementById('monsterMouth').setAttribute('ry', '10');
            };
            dropZone.ondrop = (e) => {
                e.preventDefault();
                const droppedItem = e.dataTransfer.getData('text/plain');
                handleFeedMonster(droppedItem);
            };
        }

        function setupTouchDrag(element, itemVal) {
            let initialX = 0, initialY = 0;
            let currentX = 0, currentY = 0;

            element.ontouchstart = (e) => {
                const touch = e.touches[0];
                initialX = touch.clientX;
                initialY = touch.clientY;
                element.style.position = 'fixed';
                element.style.zIndex = '1000';
                document.getElementById('monsterMouth').setAttribute('ry', '18');
            };

            element.ontouchmove = (e) => {
                e.preventDefault();
                const touch = e.touches[0];
                currentX = touch.clientX - initialX;
                currentY = touch.clientY - initialY;
                element.style.transform = `translate(${currentX}px, ${currentY}px) scale(1.1)`;
            };

            element.ontouchend = (e) => {
                const touch = e.changedTouches[0];
                const dropZone = document.getElementById('monsterDropZone');
                const rect = dropZone.getBoundingClientRect();

                element.style.position = '';
                element.style.zIndex = '';
                element.style.transform = '';
                document.getElementById('monsterMouth').setAttribute('ry', '10');

                if (
                    touch.clientX >= rect.left &&
                    touch.clientX <= rect.right &&
                    touch.clientY >= rect.top &&
                    touch.clientY <= rect.bottom
                ) {
                    handleFeedMonster(itemVal);
                }
            };
        }

        function handleFeedMonster(item) {
            const monsterSvg = document.getElementById('monsterSvg');
            const mouth = document.getElementById('monsterMouth');
            const lvl = document.getElementById('monsterLevelSelect').value;

            const isMatch = (lvl == 1) ? (item === currentMonsterTarget) : (item.toUpperCase() === currentMonsterTarget);

            if (isMatch) {
                playSound('eat');
                mouth.setAttribute('ry', '22');
                monsterSvg.classList.add('monster-happy');

                recordProgress('Feed Monster', currentMonsterTarget, true);
                showBanner("Yum Yum! Monster loved it! 👾", 'success');

                setTimeout(() => {
                    mouth.setAttribute('ry', '10');
                    monsterSvg.classList.remove('monster-happy');
                    initMonsterGame();
                }, 1200);
            } else {
                playSound('wrong');
                monsterSvg.classList.add('monster-sad');
                recordProgress('Feed Monster', currentMonsterTarget, false);
                showBanner(`Yuck! Monster wants '${currentMonsterTarget}', not '${item}'! 👹`, 'error');

                setTimeout(() => monsterSvg.classList.remove('monster-sad'), 600);
            }
        }

        // Analytics Loading
        async function loadAnalytics() {
            if (!currentProfile) return;
            const res = await fetch('/api/analytics/' + currentProfile.id);
            const data = await res.json();
            document.getElementById('totalPlayedStat').innerText = data.total_played;

            const container = document.getElementById('masteryHeatmap');
            container.innerHTML = '';
            data.mastery.forEach(m => {
                const pct = Math.round((m.correct_attempts / m.total_attempts) * 100);
                const badge = document.createElement('div');
                badge.className = 'bg-white border-2 border-amber-200 p-3 rounded-2xl flex flex-col items-center justify-center shadow-sm';
                badge.innerHTML = `
                    <span class="text-xl font-bold text-amber-600">${m.item_tested}</span>
                    <span class="text-xs text-slate-500 font-bold mt-1">${pct}% Mastered</span>
                `;
                container.appendChild(badge);
            });
        }
    </script>
</body>
</html>
"""

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