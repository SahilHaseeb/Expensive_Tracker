import json
import os
from datetime import datetime, date

BACKUP_DIR = 'storage'
BACKUP_FILE = os.path.join(BACKUP_DIR, 'app_data_backup.json')

def save_db_backup(db, User, Expense, Budget, Subscription):
    """
    Saves full snapshot of users, expenses, budgets, and subscriptions 
    to a persistent JSON storage backup.
    """
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        
        users = User.query.all()
        expenses = Expense.query.all()
        budgets = Budget.query.all()
        subscriptions = Subscription.query.all()

        backup_data = {
            "version": "1.0",
            "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "email": u.email,
                    "password_hash": u.password_hash,
                    "currency": u.currency or '₹'
                }
                for u in users
            ],
            "expenses": [
                {
                    "id": e.id,
                    "amount": e.amount,
                    "category": e.category,
                    "date": e.date.strftime('%Y-%m-%d') if isinstance(e.date, (date, datetime)) else str(e.date),
                    "note": e.note,
                    "user_id": e.user_id
                }
                for e in expenses
            ],
            "budgets": [
                {
                    "id": b.id,
                    "category": b.category,
                    "monthly_limit": b.monthly_limit,
                    "user_id": b.user_id
                }
                for b in budgets
            ],
            "subscriptions": [
                {
                    "id": s.id,
                    "name": s.name,
                    "amount": s.amount,
                    "category": s.category,
                    "billing_cycle": s.billing_cycle,
                    "next_due_date": s.next_due_date.strftime('%Y-%m-%d') if isinstance(s.next_due_date, (date, datetime)) else str(s.next_due_date),
                    "user_id": s.user_id
                }
                for s in subscriptions
            ]
        }

        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)

    except Exception as e:
        print(f"Error saving DB backup: {e}")


def restore_db_from_backup(db, User, Expense, Budget, Subscription):
    """
    Restores users, expenses, budgets, and subscriptions if the SQLite DB is fresh/empty.
    """
    try:
        if not os.path.exists(BACKUP_FILE):
            return

        with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        users_count = User.query.count()
        
        # If DB is empty, restore all data
        if users_count == 0 and data.get("users"):
            print("Restoring database from persistent storage...")
            
            # 1. Restore Users
            for u in data.get("users", []):
                user = User(
                    id=u.get("id"),
                    username=u.get("username"),
                    email=u.get("email"),
                    password_hash=u.get("password_hash"),
                    currency=u.get("currency", "₹")
                )
                db.session.add(user)
            db.session.commit()

            # 2. Restore Expenses
            for e in data.get("expenses", []):
                exp_date = datetime.strptime(e.get("date"), '%Y-%m-%d').date() if e.get("date") else date.today()
                expense = Expense(
                    id=e.get("id"),
                    amount=e.get("amount", 0.0),
                    category=e.get("category", "Other"),
                    date=exp_date,
                    note=e.get("note", ""),
                    user_id=e.get("user_id")
                )
                db.session.add(expense)
            
            # 3. Restore Budgets
            for b in data.get("budgets", []):
                budget = Budget(
                    id=b.get("id"),
                    category=b.get("category"),
                    monthly_limit=b.get("monthly_limit", 0.0),
                    user_id=b.get("user_id")
                )
                db.session.add(budget)

            # 4. Restore Subscriptions
            for s in data.get("subscriptions", []):
                sub_date = datetime.strptime(s.get("next_due_date"), '%Y-%m-%d').date() if s.get("next_due_date") else date.today()
                sub = Subscription(
                    id=s.get("id"),
                    name=s.get("name"),
                    amount=s.get("amount", 0.0),
                    category=s.get("category", "Entertainment"),
                    billing_cycle=s.get("billing_cycle", "Monthly"),
                    next_due_date=sub_date,
                    user_id=s.get("user_id")
                )
                db.session.add(sub)

            db.session.commit()
            print("Database successfully restored from backup!")

    except Exception as e:
        print(f"Error restoring DB backup: {e}")
        db.session.rollback()
