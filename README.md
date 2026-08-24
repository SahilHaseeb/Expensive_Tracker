# 💰 ExpenseAI — Smart AI & ML Personal Expense Tracker

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Render-success?style=for-the-badge&logo=render)](https://expensive-tracker-sfev.onrender.com)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-ML-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-AI%20Vision-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)

> **ExpenseAI** is a next-generation, glassmorphic financial management web application that combines **Machine Learning regression forecasting**, **Google Gemini Vision OCR receipt scanning**, **Natural Language Voice-to-Expense input**, and **real-time multi-store price comparisons** to give users complete control over their personal economy.

---

## 🌐 Live Web Application
🔗 **[https://expensive-tracker-sfev.onrender.com](https://expensive-tracker-sfev.onrender.com)**

---

## ✨ Key Features & Capabilities

### 1. 📈 Machine Learning Future Expense Predictor
- Powered by **Scikit-Learn's `LinearRegression`** algorithm.
- Analyzes user's historical month-by-month spending trends.
- Automatically generates individualized `.joblib` model weights per user to forecast next month's total spending.

### 2. 📸 AI Receipt & Invoice Scanner (OCR + Vision)
- Drag-and-drop receipt or shopping bill photos.
- **Google Gemini Vision** automatically extracts the merchant name, transaction date, category, and total amount with 1-click form auto-fill.

### 3. 🗣️ Voice-to-Expense Speech Input
- Integrated with the **Web Speech API** and natural language heuristic parsing.
- Speak naturally (*"Spent 1500 on dinner with friends"* or *"Paid 400 for Uber"*), and the system automatically categorizes and logs the expense.

### 4. 🤖 AI Financial Advisor Chatbot
- Interactive AI advisor providing personalized budgeting strategies, tax optimization tips, and debt reduction plans based on the user's live database spending patterns.

### 5. 🛒 Live Shopping Price Finder & Deals Comparison
- Real-time product search across top retailers (**Amazon, Flipkart, Sephora, Daraz, Walmart, eBay**).
- 3-Way Sorting (Lowest Price First, Highest Customer Rating, Premium/High-End).
- Direct store product links to buy immediately at the best discount.

### 6. 🎯 Category Budget Limits & Spending Caps
- Set custom monthly limits per category (Food, Transport, Rent, Shopping, Entertainment, etc.).
- Color-coded progress meters alert you:
  - 🟢 **Safe:** Under 75%
  - 🟡 **Warning:** 75% – 99%
  - 🔴 **Over Budget Alert:** 100%+

### 7. 🔄 Recurring Subscriptions & Bill Reminders
- Track recurring services (Netflix, Spotify, Gym, WiFi, Electricity).
- Visual countdown badges and prominent dashboard banners alert users 3 days before any bill is due.

### 8. ⭐ Financial Health Score (0 – 100)
- Real-time circular gauge measuring budget discipline, spending volatility, and category balance.
- Provides actionable AI financial health tips.

### 9. 💱 Multi-Currency Support
- Switch seamlessly between **₹ (INR), Rs. (PKR), $ (USD), € (EUR), £ (GBP), AED, and SAR**.

### 10. 📄 High-Resolution PDF Monthly Statement
- Generates a print-ready, itemized financial summary statement with category analytics and health score badge.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend Framework** | Python, Flask, Flask-Login, Flask-SQLAlchemy |
| **Machine Learning** | Scikit-Learn (LinearRegression, NumPy, Pandas, Joblib) |
| **Artificial Intelligence** | Google Gemini 1.5 Flash (Vision OCR + Chatbot) |
| **Database** | SQLite / SQLAlchemy ORM with Auto-Migrations |
| **Data Visualizations** | Plotly.js Interactive Charts |
| **Frontend UI** | HTML5, Modern Vanilla CSS (Glassmorphism & Dark/Light Mode), JavaScript |
| **Deployment** | Gunicorn WSGI, Render Cloud Platform |

---

## 📁 Repository Structure

```text
Expensive_Tracker/
├── app/
│   ├── static/
│   │   ├── css/
│   │   │   ├── style.css             # Glassmorphism & dark/light theme tokens
│   │   │   └── animations.css        # Keyframes & floating animations
│   │   └── js/
│   │       ├── receipt-scanner.js    # Drag-and-drop OCR upload handler
│   │       ├── voice-expense.js      # Web Speech API recorder
│   │       ├── chatbot.js            # AI advisor chat client
│   │       └── theme-toggle.js       # Zero-flash dark mode switcher
│   ├── templates/
│   │   ├── base.html                 # Master navigation & currency dropdown
│   │   ├── landing.html              # SaaS homepage with About & Contact
│   │   ├── dashboard.html            # Main dashboard with Health Score & Charts
│   │   ├── add_expense.html          # Add expense with OCR dropzone
│   │   ├── budgets.html              # Category spending limits manager
│   │   ├── subscriptions.html        # Recurring bill tracker
│   │   ├── shopping.html             # Multi-store price comparison engine
│   │   ├── chatbot.html              # AI financial chatbot interface
│   │   ├── statement_pdf.html        # Print-ready monthly statement
│   │   ├── login.html                # Auth login
│   │   └── register.html             # Auth register
│   ├── __init__.py                   # App factory & DB auto-migrations
│   ├── models.py                     # User, Expense, Budget, Subscription models
│   ├── routes.py                     # Core CRUD & Contact form routes
│   ├── auth.py                       # User authentication & session handling
│   ├── ml_utils.py                   # Scikit-Learn ML regression forecasting
│   ├── ai_advisor.py                 # Google Gemini AI financial logic
│   ├── receipt_scanner.py            # Gemini Vision OCR receipt parser
│   ├── shopping_service.py           # Multi-store live deal comparison engine
│   ├── feature_routes.py             # Budgets, Subscriptions, OCR & Voice APIs
│   └── analytics.py                  # Financial Health Score engine
├── config.py                         # Environment variables configuration
├── requirements.txt                  # Python dependencies
├── Procfile                          # Cloud deployment process file
├── wsgi.py                           # Production entry point
├── run.py                            # Development server runner
└── README.md                         # Project documentation
```

---

## ⚙️ Quickstart (Run Locally)

### 1. Clone the Repository
```bash
git clone https://github.com/SahilHaseeb/Expensive_Tracker.git
cd Expensive_Tracker
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. (Optional) Set Environment Variables
Create a `.env` file in the root folder:
```env
SECRET_KEY=your_secret_key
GEMINI_API_KEY=your_gemini_api_key
SERPAPI_API_KEY=your_serpapi_key
```

### 5. Run the Application
```bash
python run.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 👨‍💻 Author & Developer

**Sahil Haseeb**
* 📍 **Location:** New Garden Town, Lahore, Pakistan
* 📧 **Email:** [haseebsahil0081@gmail.com](mailto:haseebsahil0081@gmail.com)
* 📞 **WhatsApp / Phone:** [+92 328 4538632](https://wa.me/923284538632)

---

## 📄 License
This project is open source and available under the [MIT License](LICENSE).
