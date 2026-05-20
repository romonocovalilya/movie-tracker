from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super-secret-key-change-it-in-production'
# Безопасный путь для записи базы данных в системную папку хостинга
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join('/tmp', 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ВАЖНО: Создание таблиц перенесено сюда, чтобы сервер Gunicorn точно увидел обновление
with app.app_context():
    db.drop_all()   # Стирает старую конфликтную структуру таблиц
    db.create_all() # Создает новые таблицы с полями под постеры и описания

login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==========================================================================
# МОДЕЛИ ТАБЛИЦ БАЗЫ ДАННЫХ
# ==========================================================================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    franchises = db.relationship('Franchise', backref='owner', lazy=True)
    progress = db.relationship('UserProgress', backref='user', lazy=True)

class Franchise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_items = db.relationship('MediaItem', backref='franchise', lazy=True)

class MediaItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    timeline = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    poster_url = db.Column(db.String(500), default='')   # Новая колонка
    description = db.Column(db.Text, default='')          # Новая колонка
    franchise_id = db.Column(db.Integer, db.ForeignKey('franchise.id'), nullable=False)

class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media_item.id'), nullable=False)
    is_watched = db.Column(db.Boolean, default=False)
    rating = db.Column(db.String(10), default='none')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================================================
# МАРШРУТЫ АВТОРИЗАЦИИ
# ==========================================================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!')
            return redirect(url_for('register'))
        new_user = User(username=username, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Неверное имя пользователя или пароль!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================================================
# РАБОТА С АПИ ДАННЫХ
# ==========================================================================
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)

@app.route('/api/data')
@login_required
def get_data():
    franchises = Franchise.query.filter_by(user_id=current_user.id).all()
    progress_items = UserProgress.query.filter_by(user_id=current_user.id).all()
    
    watched_ids = [p.media_id for p in progress_items if p.is_watched]
    likes = [p.media_id for p in progress_items if p.rating == 'like']
    dislikes = [p.media_id for p in progress_items if p.rating == 'dislike']
    
    db_dict = {}
    titles_dict = {}
    for f in franchises:
        db_dict[f.id] = []
        titles_dict[f.id] = f.name
        for item in f.media_items:
            db_dict[f.id].append({
                "id": item.id, "title": item.title, "type": item.media_type,
                "year": item.year, "timeline": item.timeline, "video": item.video_url,
                "poster": item.poster_url, "description": item.description
            })
    return jsonify({"db": db_dict, "titles": titles_dict, "watched": watched_ids, "likes": likes, "dislikes": dislikes})

@app.route('/api/franchise', methods=['POST'])
@login_required
def add_franchise():
    name = request.json.get('name')
    if name:
        new_f = Franchise(name=name, user_id=current_user.id)
        db.session.add(new_f)
        db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/media', methods=['POST'])
@login_required
def add_media():
    data = request.json
    video_url = data.get('video')
    if 'watch?v=' in video_url:
        video_url = video_url.replace('watch?v=', 'embed/')
    new_item = MediaItem(
        title=data.get('title'), media_type=data.get('type'), year=int(data.get('year')),
        timeline=data.get('timeline'), video_url=video_url, franchise_id=int(data.get('franchise_id')),
        poster_url=data.get('poster', ''), description=data.get('description', '')
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"status": "success"})

@app.route('/api/rate', methods=['POST'])
@login_required
def rate_media():
    data = request.json
    m_id = int(data.get('id'))
    rate_type = data.get('type')
    prog = UserProgress.query.filter_by(user_id=current_user.id, media_id=m_id).first()
    if not prog:
        prog = UserProgress(user_id=current_user.id, media_id=m_id)
        db.session.add(prog)
    if rate_type == 'watch':
        prog.is_watched = not prog.is_watched
    elif rate_type == 'like':
        prog.rating = 'none' if prog.rating == 'like' else 'like'
    elif rate_type == 'dislike':
        prog.rating = 'none' if prog.rating == 'dislike' else 'dislike'
    db.session.commit()
    return jsonify({"status": "success"})

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
