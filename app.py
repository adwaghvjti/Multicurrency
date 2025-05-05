from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import requests
import razorpay
import secrets
from bson.objectid import ObjectId
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from email_validator import validate_email, EmailNotValidError
from razorpay_gateway import create_razorpay_order
from config import NEWS_API_KEY, NEWS_API_URL, RAZORPAY_KEY_ID, EXCHANGE_API_URL, IMPORTANT_CURRENCIES, users_collection, transactions_collection
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
import base64

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
# Flask-Bcrypt for password hashing
bcrypt = Bcrypt(app)

# Flask-Login for session management
login_manager = LoginManager(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, user_id, email, phone, password):
        self.id = user_id
        self.email = email
        self.phone = phone
        self.password = password
        self.balance = self.get_balance()
    
    def get_balance(self):
        user_data = users_collection.find_one({"_id": ObjectId(self.id)})
        return user_data.get('balance', 0.0) if user_data else 0.0

@login_manager.user_loader
def load_user(user_id):
    user_data = users_collection.find_one({"_id": ObjectId(user_id)})
    if user_data:
        return User(user_id=str(user_data["_id"]), email=user_data["email"], phone=user_data["phone"], password=user_data["password"])
    return None

@app.route('/')
def home():
    query = request.args.get('query', 'money AND currencies')
    params = {
        'q': query,
        'apiKey': NEWS_API_KEY,
        'language': 'en',
        'sortBy': 'publishedAt'
    }
    
    try:
        response = requests.get(NEWS_API_URL, params=params)
        news_data = response.json()
    except Exception:
        news_data = {"articles": []}
        
    return render_template('home.html', articles=news_data.get('articles', []))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validate email
        try:
            validate_email(email)
        except EmailNotValidError as e:
            flash(str(e), 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('register'))

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = {
            "email": email,
            "phone": phone,
            "password": hashed_password,
            "balance": 0.0
        }
        users_collection.insert_one(user)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        user_data = users_collection.find_one({"email": email})
        if user_data and bcrypt.check_password_hash(user_data["password"], password):
            user = User(user_id=str(user_data["_id"]), email=user_data["email"], phone=user_data["phone"], password=user_data["password"])
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Login failed, check your email and password', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'success')
    return redirect(url_for('login'))

@app.route('/wallet')
@login_required
def wallet():
    # Get exchange rates for INR
    try:
        response = requests.get(f"{EXCHANGE_API_URL}INR")
        exchange_data = response.json()
        rates = {currency: exchange_data['rates'].get(currency) for currency in IMPORTANT_CURRENCIES}
    except Exception as e:
        flash(f"Error fetching exchange rates: {str(e)}", 'danger')
        rates = {}
    
    return render_template('wallet.html', balance=current_user.balance, rates=rates)

@app.route('/wallet/deposit', methods=['POST'])
@login_required
def deposit():
    amount = request.form.get('amount', type=float)
    if amount and amount > 0:
        # Create Razorpay order
        order = create_razorpay_order(amount)
        
        return render_template('checkout.html', order_id=order['id'], amount=amount, key_id=RAZORPAY_KEY_ID)
    else:
        flash('Invalid deposit amount', 'danger')
    return redirect(url_for('wallet'))

@app.route('/wallet/withdraw', methods=['POST'])
@login_required
def withdraw():
    amount = request.form.get('amount', type=float)
    if amount and 0 < amount <= current_user.balance:
        new_balance = current_user.balance - amount
        users_collection.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"balance": new_balance}})
        current_user.balance = new_balance
        # Store transaction in MongoDB
        transaction = {
            'type': 'withdraw',
            'amount': amount,
            'balance': current_user.balance,
            'email': current_user.email,
            'phone': current_user.phone
        }
        transactions_collection.insert_one(transaction)
        flash(f'Successfully withdrew ₹{amount:.2f}', 'success')
    else:
        flash('Invalid withdrawal amount or insufficient balance', 'danger')
    return redirect(url_for('wallet'))

@app.route('/wallet/convert', methods=['POST'])
@login_required
def convert_currency():
    target_currency = request.form.get('currency')
    amount = request.form.get('convert_amount', type=float)
    
    if not target_currency or not amount or amount <= 0 or amount > current_user.balance:
        flash('Invalid conversion amount or insufficient balance', 'danger')
        return redirect(url_for('wallet'))
    
    try:
        # Get current exchange rate
        response = requests.get(f"{EXCHANGE_API_URL}INR")
        exchange_data = response.json()
        
        if target_currency not in exchange_data['rates']:
            flash(f'Currency {target_currency} not available for conversion', 'danger')
            return redirect(url_for('wallet'))
        
        rate = exchange_data['rates'][target_currency]
        converted_amount = amount * rate  # INR to target currency
        
        # Store transaction
        transaction = {
            'type': 'currency_conversion',
            'from_currency': 'INR',
            'to_currency': target_currency,
            'amount_inr': amount,
            'amount_converted': converted_amount,
            'rate': rate,
            'email': current_user.email,
            'phone': current_user.phone
        }
        transactions_collection.insert_one(transaction)
        
        # Update user balance
        new_balance = current_user.balance - amount
        users_collection.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"balance": new_balance}})
        current_user.balance = new_balance
        
        flash(f'Successfully converted ₹{amount:.2f} to {converted_amount:.2f} {target_currency}', 'success')
    except Exception as e:
        flash(f'Error during currency conversion: {str(e)}', 'danger')
    
    return redirect(url_for('wallet'))

@app.route('/wallet/payment_success', methods=['POST'])
@login_required
def payment_success():
    payment_id = request.form.get('razorpay_payment_id')
    order_id = request.form.get('razorpay_order_id')
    amount = request.form.get('amount', type=float)
    
    # Verify payment
    try:
        new_balance = current_user.balance + amount
        users_collection.update_one({"_id": ObjectId(current_user.id)}, {"$set": {"balance": new_balance}})
        current_user.balance = new_balance
        # Store transaction in MongoDB
        transaction = {
            'type': 'deposit',
            'amount': amount,
            'balance': current_user.balance,
            'payment_id': payment_id,
            'order_id': order_id,
            'email': current_user.email,
            'phone': current_user.phone
        }
        transactions_collection.insert_one(transaction)
        flash(f'Successfully deposited ₹{amount:.2f}', 'success')
    except Exception as e:
        flash(f'Payment verification failed: {str(e)}', 'danger')
    
    return redirect(url_for('wallet'))

@app.route('/exchange')
def exchange_rates():
    base_currency = request.args.get('base_currency', 'INR')
    try:
        response = requests.get(f"{EXCHANGE_API_URL}{base_currency}")
        exchange_data = response.json()
        rates = {currency: exchange_data['rates'].get(currency) for currency in IMPORTANT_CURRENCIES}
    except Exception as e:
        flash(f"Error fetching exchange rates: {str(e)}", 'danger')
        rates = {}
    
    return render_template('exchange.html', base_currency=base_currency, rates=rates)

@app.route('/exchange/graph')
def exchange_graph():
    base_currency = request.args.get('base_currency', 'INR')
    try:
        response = requests.get(f"{EXCHANGE_API_URL}{base_currency}")
        exchange_data = response.json()
        
        # Filter currencies for display
        currencies = []
        rates = []
        for currency in IMPORTANT_CURRENCIES:
            if currency != base_currency and currency in exchange_data['rates']:
                currencies.append(currency)
                rates.append(exchange_data['rates'][currency])
        
        # Create graph
        plt.figure(figsize=(10, 6))
        plt.bar(currencies, rates, color='skyblue')
        plt.xlabel('Currency')
        plt.ylabel(f'Rate (1 {base_currency} to X)')
        plt.title(f'Exchange Rates for {base_currency}')
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Convert to base64 for embedding in HTML
        img = BytesIO()
        plt.savefig(img, format='png')
        img.seek(0)
        plot_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close()
        
        return render_template('exchange_graph.html', plot_url=plot_url, base_currency=base_currency)
    except Exception as e:
        flash(f"Error generating exchange rate graph: {str(e)}", 'danger')
        return redirect(url_for('exchange_rates'))

# Optional: Add health check endpoint for Vercel
@app.route('/health')
def health_check():
    return jsonify({"status": "ok"})
