from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User
import json
import os
from datetime import datetime

auth = Blueprint('auth', __name__)

def save_user_to_json(username, email, password_hash):
    """Save registered user data to JSON file"""
    try:
        user_data_dir = 'user_data'
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)
        
        json_file = os.path.join(user_data_dir, 'registered_users.json')
        
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                users = json.load(f)
        else:
            users = []
        
        users.append({
            'username': username,
            'email': email,
            'password_hash': password_hash,
            'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'ip_address': request.remote_addr
        })
        
        with open(json_file, 'w') as f:
            json.dump(users, f, indent=4)
    except Exception as e:
        print(f"Error saving to JSON: {e}")

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
        
        # Save to JSON file backup
        save_user_to_json(username, email, user.password_hash)
        
        # Automatically log in the user upon registration
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
        remember = True if request.form.get('remember') else False

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
            flash('Invalid username/email or password! If you recently redeployed, please click "Create an account" to register.', 'error')
    
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))