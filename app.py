import hashlib
import json
import random
from PIL import Image
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Измените на реальный секретный ключ
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# Класс пользователя
class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['name']  # Теперь id это имя пользователя
        self.name = user_data['name']
        self.phone = user_data['phone']
        self.password_hash = user_data['password']
        self.money = user_data.get('money', 0)
        self.card_number = user_data.get('card_number', '')
        self.country = user_data.get('country', '')


def load_users():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_users(users):
    with open('data.json', 'w') as f:
        json.dump(users, f, indent=4)


@login_manager.user_loader
def load_user(user_id):
    users = load_users()
    # Ищем пользователя по имени
    for user_data in users.values():
        if user_data['name'] == user_id:
            return User(user_data)
    return None


@app.route('/')
@login_required
def index():
    users = load_users()
    # Сортировка пользователей по количеству денег
    leaderboard = sorted(users.values(), key=lambda x: x.get('money', 0), reverse=True)
    return render_template('index.html', leaderboard=leaderboard)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        password = request.form['password']
        country = request.form['country']

        users = load_users()

        # Проверка уникальности имени
        for user_data in users.values():
            if user_data['name'].lower() == name.lower():
                flash('Это имя уже занято. Пожалуйста, выберите другое.')
                return redirect(url_for('register'))

        if phone in users:
            flash('Этот номер телефона уже зарегистрирован')
            return redirect(url_for('register'))

        # Генерация случайного номера карты
        card_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])

        users[phone] = {
            'name': name,
            'phone': phone,
            'password': generate_password_hash(password),
            'money': 0,
            'card_number': card_number,
            'country': country
        }
        save_users(users)

        user = User(users[phone])
        login_user(user)
        return redirect(url_for('index'))

    return render_template('register.html')
    # return render_template('registration.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        users = load_users()
        user_found = None

        # Ищем пользователя по имени
        for user_data in users.values():
            if user_data['name'].lower() == username.lower():
                user_found = user_data
                break

        if not user_found:
            flash('Пользователь с таким именем не найден')
            return redirect(url_for('login'))

        if not check_password_hash(user_found['password'], password):
            flash(f'Пароль занят пользователем {user_found["name"]}')
            return redirect(url_for('login'))

        user = User(user_found)
        login_user(user)
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/get_money', methods=['POST'])
@login_required
def get_money():
    users = load_users()
    amount = random.randint(100, 1000)

    # Ищем пользователя по имени
    for user_data in users.values():
        if user_data['name'] == current_user.name:
            user_data['money'] = user_data.get('money', 0) + amount
            break

    save_users(users)
    return jsonify({'success': True, 'amount': amount})


@app.route('/admin_panel')
@login_required
def admin_panel():
    return render_template('admin.html')


@app.route('/verify_admin_image', methods=['POST'])
@login_required
def verify_admin_image():
    if 'image' not in request.files:
        return jsonify({'success': False, 'error': 'Изображение не найдено'})

    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})

    try:
        # Загружаем изображение пользователя
        user_image = Image.open(file)
        user_image_hash = hashlib.md5(user_image.tobytes()).hexdigest()

        # Загружаем эталонное изображение
        reference_image = Image.open('static/image1.jpg')
        reference_hash = hashlib.md5(reference_image.tobytes()).hexdigest()

        # Сравниваем хеши изображений
        is_match = user_image_hash == reference_hash

        return jsonify({'success': is_match})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/admin/get_database')
@login_required
def get_database():
    try:
        users = load_users()
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/update_database', methods=['POST'])
@login_required
def update_database():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Файл не найден'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'Файл не выбран'})

    try:
        # Читаем JSON из загруженного файла
        new_data = json.loads(file.read().decode('utf-8'))

        # Проверяем структуру данных
        for phone, user_data in new_data.items():
            required_fields = ['name', 'phone', 'password', 'money', 'card_number', 'country']
            if not all(field in user_data for field in required_fields):
                return jsonify({'success': False, 'error': 'Неверная структура данных'})

        # Сохраняем новые данные
        save_users(new_data)
        return jsonify({'success': True})
    except json.JSONDecodeError:
        return jsonify({'success': False, 'error': 'Неверный формат JSON'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Маршрут для отображения страницы с колесом фортуны
@app.route('/casino')
@login_required
def casino_page():
    return render_template('casino.html')
MAX_SPINS = 10
# Маршрут для обработки кручения колеса
@app.route('/casino', methods=['POST'])
@login_required
def casino():
    users = load_users()

    # Находим текущего пользователя по имени
    for phone, user_data in users.items():
        if user_data['name'] == current_user.name:
            break

    # Проверяем, сколько раз пользователь уже крутил колесо
    spins_count = user_data.get('spins_count', 0)

    # Если достигнут лимит кручений (10 раз), сбрасываем баланс и счетчик
    if spins_count >= MAX_SPINS:
        user_data['money'] = 0  # Сбрасываем баланс до 0
        user_data['spins_count'] = 0  # Сбрасываем счетчик кручений
        save_users(users)
        return jsonify({
            'result': 'Лимит кручений достигнут. Баланс сброшен.',
            'balance': user_data['money'],
            'final_spin': True,
            'message': 'Не в этот раз'  # Сообщение для главной страницы
        })

    # Генерируем случайный результат кручения колеса
    results = [-20000] * 9 + [180000]  # 9 секторов с -20k и 1 сектор с +180k
    result = random.choice(results)

    # Обновляем баланс пользователя
    user_data['money'] += result  # Добавляем/вычитаем сумму из баланса
    user_data['spins_count'] = spins_count + 1  # Увеличиваем счетчик кручений

    # Сохраняем обновленные данные
    save_users(users)

    # Проверяем, является ли это последним кручением
    is_final_spin = (user_data['spins_count'] == MAX_SPINS)

    # Формируем ответ для клиента
    response_data = {
        'result': result,  # Результат текущего кручения (+180k или -20k)
        'balance': user_data['money'],  # Текущий баланс пользователя
        'final_spin': is_final_spin,  # Флаг последнего кручения
        'message': 'Не в этот раз' if is_final_spin else None  # Сообщение для главной страницы
    }

    return jsonify(response_data)

if __name__ == '__main__':
    app.run(debug=True)
