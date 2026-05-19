from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
# Секретный ключ для защиты сессий и куки пользователей от подделки
app.config['SECRET_KEY'] = 'super-secret-key-change-it-in-production'
# Путь к локальной файловой базе данных SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
# Перенаправляет гостей на страницу входа, если они пытаются открыть сайт без авторизации
login_manager.login_view = 'login'

# ==========================================================================
# 1. СТРУКТУРА ТАБЛИЦ БАЗЫ ДАННЫХ (МОДЕЛИ)
# ==========================================================================

# Таблица пользователей (хранит аккаунты)
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False) # Пароли хранятся только в зашифрованном виде
    
    # Связи с созданными хронологиями и отметками прогресса
    franchises = db.relationship('Franchise', backref='owner', lazy=True)
    progress = db.relationship('UserProgress', backref='user', lazy=True)

# Таблица киновселенных / хронологий (например: Марвел, Звездные Войны)
class Franchise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_items = db.relationship('MediaItem', backref='franchise', lazy=True)

# Таблица конкретных видеокарточек (фильмов, сериалов и т.д.) внутри хронологий
class MediaItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    media_type = db.Column(db.String(20), nullable=False) # movie, series, cartoon, animated_series
    year = db.Column(db.Integer, nullable=False)
    timeline = db.Column(db.String(100), nullable=False)
    video_url = db.Column(db.String(500), nullable=False)
    franchise_id = db.Column(db.Integer, db.ForeignKey('franchise.id'), nullable=False)

# Таблица личного прогресса (сохраняет лайки, дизлайки и галочки просмотра для каждого юзера)
class UserProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey('media_item.id'), nullable=False)
    is_watched = db.Column(db.Boolean, default=False)
    rating = db.Column(db.String(10), default='none') # может быть: like, dislike, none

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================================================
# 2. МАРШРУТЫ АВТОРИЗАЦИИ И БЕЗОПАСНОСТИ (HTML)
# ==========================================================================

# Регистрация нового аккаунта
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        # Проверяем, занято ли имя пользователя
        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует!')
            return redirect(url_for('register'))
            
        # Хэшируем (шифруем) пароль перед сохранением в базу
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password_hash=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        
        # Автоматически авторизуем пользователя после успешного создания профиля
        login_user(new_user)
        return redirect(url_for('index'))
        
    return render_template('register.html')

# Вход в существующий аккаунт
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # Сверяем зашифрованный хэш из базы с введенным паролем
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
            
        flash('Неверное имя пользователя или пароль!')
        
    return render_template('login.html')

# Выход из личного кабинета
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ==========================================================================
# 3. МАРШРУТЫ ГЛАВНОЙ СТРАНИЦЫ И API СВЯЗИ
# ==========================================================================

# Главная страница личного кинотеатра (доступна только после авторизации)
@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)

# API-эндпоинт: Выдает фронтенду все сохраненные хронологии и прогресс текущего юзера
@app.route('/api/data')
@login_required
def get_data():
    franchises = Franchise.query.filter_by(user_id=current_user.id).all()
    progress_items = UserProgress.query.filter_by(user_id=current_user.id).all()
    
    # Фильтруем массивы отметок для передачи в JS
    watched_ids = [p.media_id for p in progress_items if p.is_watched]
    likes = [p.media_id for p in progress_items if p.rating == 'like']
    dislikes = [p.media_id for p in progress_items if p.rating == 'dislike']
    
    db_dict = {}
    titles_dict = {}
    
    # Переводим данные из таблиц базы данных в формат JSON-объекта
    for f in franchises:
        db_dict[f.id] = []
        titles_dict[f.id] = f.name
        for item in f.media_items:
            db_dict[f.id].append({
                "id": item.id,
                "title": item.title,
                "type": item.media_type,
                "year": item.year,
                "timeline": item.timeline,
                "video": item.video_url
            })
            
    return jsonify({
        "db": db_dict,
        "titles": titles_dict,
        "watched": watched_ids,
        "likes": likes,
        "dislikes": dislikes
    })

# API-эндпоинт: Создание новой вкладки-хронологии
@app.route('/api/franchise', methods=['POST'])
@login_required
def add_franchise():
    name = request.json.get('name')
    if name:
        new_f = Franchise(name=name, user_id=current_user.id)
        db.session.add(new_f)
        db.session.commit()
    return jsonify({"status": "success"})

# API-эндпоинт: Добавление новой видеокарточки (фильма/сериала)
@app.route('/api/media', methods=['POST'])
@login_required
def add_media():
    data = request.json
    video_url = data.get('video')
    
    # Автоматически переписываем обычную ссылку YouTube в рабочий формат плеера iframe
    if 'watch?v=' in video_url:
        video_url = video_url.replace('watch?v=', 'embed/')
        
    new_item = MediaItem(
        title=data.get('title'),
        media_type=data.get('type'),
        year=int(data.get('year')),
        timeline=data.get('timeline'),
        video_url=video_url,
        franchise_id=int(data.get('franchise_id'))
    )
    db.session.add(new_item)
    db.session.commit()
    return jsonify({"status": "success"})

# API-эндпоинт: Обработка кликов по кнопкам "Просмотрено", "Лайк" и "Дизлайк"
@app.route('/api/rate', methods=['POST'])
@login_required
def rate_media():
    data = request.json
    m_id = int(data.get('id'))
    rate_type = data.get('type') # 'watch', 'like' или 'dislike'
    
    # Ищем, была ли уже запись прогресса для этого фильма у текущего пользователя
    prog = UserProgress.query.filter_by(user_id=current_user.id, media_id=m_id).first()
    if not prog:
        # Если записи нет, создаем новую пустую строку прогресса
        prog = UserProgress(user_id=current_user.id, media_id=m_id)
        db.session.add(prog)
        
    # Изменяем состояние в зависимости от нажатой кнопки
    if rate_type == 'watch':
        prog.is_watched = not prog.is_watched
    elif rate_type == 'like':
        prog.rating = 'none' if prog.rating == 'like' else 'like'
    elif rate_type == 'dislike':
        prog.rating = 'none' if prog.rating == 'dislike' else 'dislike'
        
    db.session.commit()
    return jsonify({"status": "success"})

# ==========================================================================
# 4. ЗАПУСК ПРИЛОЖЕНИЯ
# ==========================================================================
if __name__ == '__main__':
    with app.app_context():
        db.create_all() # Инициализирует и создает таблицы в файле database.db при первом пуске
        
    # Блок автоматического открытия локального сайта в браузере при старте
    import webbrowser
    webbrowser.open("http://127.0.0.1:5000")
    
    # Запуск веб-сервера
    app.run(debug=True, use_reloader=False)
