import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import joblib
import os
from datetime import datetime, timedelta

MODEL_DIR = 'ml_models'
if not os.path.exists(MODEL_DIR):
    os.makedirs(MODEL_DIR)

def get_monthly_expenses(user_id, expenses):
    """Convert expenses list to monthly total DataFrame"""
    df = pd.DataFrame([(e.amount, e.date) for e in expenses], columns=['amount', 'date'])
    if df.empty:
        return pd.DataFrame(columns=['month_idx', 'total'])
    df['date'] = pd.to_datetime(df['date'])
    df['month'] = df['date'].dt.to_period('M')
    monthly = df.groupby('month')['amount'].sum().reset_index()
    monthly['month_idx'] = range(1, len(monthly)+1)  # 1,2,3...
    return monthly[['month_idx', 'amount']].rename(columns={'amount': 'total'})

def train_model(user_id, expenses):
    """Train LinearRegression on monthly data"""
    monthly_df = get_monthly_expenses(user_id, expenses)
    if len(monthly_df) < 2:
        return None  # Not enough data
    X = monthly_df[['month_idx']]
    y = monthly_df['total']
    model = LinearRegression()
    model.fit(X, y)
    # Save model
    model_path = os.path.join(MODEL_DIR, f'model_{user_id}.joblib')
    joblib.dump(model, model_path)
    return model

def load_model(user_id):
    model_path = os.path.join(MODEL_DIR, f'model_{user_id}.joblib')
    if os.path.exists(model_path):
        return joblib.load(model_path)
    return None

def delete_model(user_id):
    model_path = os.path.join(MODEL_DIR, f'model_{user_id}.joblib')
    if os.path.exists(model_path):
        os.remove(model_path)

def predict_next_month(user_id, expenses):
    """Predict next month's expense. Returns (predicted_value, model_exists)."""
    model = load_model(user_id)
    if model is None:
        model = train_model(user_id, expenses)
    if model is None:
        return None  # not enough data

    monthly_df = get_monthly_expenses(user_id, expenses)
    next_month_idx = monthly_df['month_idx'].max() + 1
    predicted = model.predict([[next_month_idx]])[0]
    return round(predicted, 2)