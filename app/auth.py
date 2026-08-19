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
    user_data_dir = 'user_data'
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    
    json_file = os.path.join(user_data_dir, 'registered_users.json')
    
    # Load existing data
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            users = json.load(f)
    else:
        users = []
    
    # Add new user
    users.append({
        'username': username,
        'email': email,
        'password_hash': password_hash,
        'registration_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'ip_address': request.remote_addr
    })
    
    # Save back to file
    with open(json_file, 'w') as f:
        json.dump(users, f, indent=4)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check existing
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'error')
            return redirect(url_for('auth.register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Save to JSON file
        save_user_to_json(username, email, user.password_hash)
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=remember)
            flash(f'Welcome back, {user.username}! 👋', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    return render_template('login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out!', 'info')
    return redirect(url_for('auth.login'))