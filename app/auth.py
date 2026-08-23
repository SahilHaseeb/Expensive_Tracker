from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, Expense, Budget, Subscription
from app.db_sync import save_db_backup

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('auth.register'))

        # Case-insensitive duplicate check
        if User.query.filter(db.func.lower(User.username) == username.lower()).first():
            flash('Username already exists! Please choose another.', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter(db.func.lower(User.email) == email).first():
            flash('Email already registered! Please log in.', 'error')
            return redirect(url_for('auth.login'))

        user = User(username=username, email=email, currency='₹')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Save immediate persistent snapshot
        try:
            save_db_backup(db, User, Expense, Budget, Subscription)
        except Exception as e:
            print(f"Error syncing backup on register: {e}")

        # Automatically log in the user upon registration with 30-day cookie
        login_user(user, remember=True)
        flash(f'Account created successfully! Welcome, {user.username} 🎉', 'success')
        return redirect(url_for('main.dashboard'))

    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = True  # Always remember user session

        if not login_input or not password:
            flash('Please enter both username/email and password.', 'error')
            return render_template('login.html')

        # Allow login via EITHER Username OR Email (case-insensitive)
        user = User.query.filter(
            (db.func.lower(User.username) == login_input.lower()) | 
            (db.func.lower(User.email) == login_input.lower())
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}! 👋', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username/email or password. Please verify your credentials and try again.', 'error')
    
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))