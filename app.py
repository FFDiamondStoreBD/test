import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "your_super_secret_key"

# Supabase Setup
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Packages Data
VIP_PACKAGES = {
    "VIP_1": {"price": 500, "daily_profit": 50, "mead_days": 30},
    "VIP_2": {"price": 1000, "daily_profit": 110, "mead_days": 30},
    "VIP_3": {"price": 2000, "daily_profit": 230, "mead_days": 30},
    "VIP_4": {"price": 5000, "daily_profit": 600, "mead_days": 30},
    "VIP_5": {"price": 10000, "daily_profit": 1300, "mead_days": 30},
}

@app.route('/')
def index():
    # Fetch top earners and referrers for the landing page
    top_earners = supabase.table("users").select("name, total_earned").order("total_earned", desc=True).limit(5).execute()
    top_referrers = supabase.table("users").select("name, total_referrals").order("total_referrals", desc=True).limit(5).execute()
    proofs = supabase.table("proofs").select("*").order("created_at", desc=True).limit(10).execute()
    
    return render_template('index.html', earners=top_earners.data, referrers=top_referrers.data, proofs=proofs.data)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        referred_by = request.form.get('referral_code', '')
        my_ref_code = str(uuid.uuid4())[:8].upper()

        # Insert User
        user_data = {
            "name": name, "phone": phone, "email": email, 
            "password_hash": password, "referral_code": my_ref_code, 
            "referred_by": referred_by
        }
        res = supabase.table("users").insert(user_data).execute()
        
        if res.data:
            user_id = res.data[0]['id']
            # Give FREE Package automatically
            supabase.table("user_packages").insert({
                "user_id": user_id, 
                "package_name": "FREE",
                "last_claim_time": "2000-01-01T00:00:00" # Ready to claim
            }).execute()
            
            flash("Registration Successful! Please login.", "success")
            return redirect(url_for('login'))
            
    return render_template('register.html')

# --- NEW: History Page ---
@app.route('/history')
def history():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    withdraw_res = supabase.table("withdrawals").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    
    return render_template('history.html', user=user, withdrawals=withdraw_res.data)

# --- NEW: Referral & Team Page ---
@app.route('/referrals')
def referrals():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    # যারা এই ইউজারের রেফার কোড দিয়ে জয়েন করেছে তাদের ডাটা বের করা হচ্ছে
    team_res = supabase.table("users").select("name, created_at, is_vip").eq("referred_by", user['referral_code']).order("created_at", desc=True).execute()
    
    return render_template('referrals.html', user=user, team=team_res.data)
    
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    # User data
    user_res = supabase.table("users").select("*").eq("id", session['user_id']).execute()
    user = user_res.data[0]
    
    # Packages
    pkg_res = supabase.table("user_packages").select("*").eq("user_id", session['user_id']).execute()
    
    # Withdraw History
    withdraw_res = supabase.table("withdrawals").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    
    return render_template('dashboard.html', user=user, packages=pkg_res.data, vip=VIP_PACKAGES, withdrawals=withdraw_res.data)

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    method = request.form.get('method')
    account_number = request.form.get('account_number')
    amount = float(request.form.get('amount'))
    
    user = supabase.table("users").select("balance").eq("id", user_id).execute().data[0]
    
    # শর্ত: সর্বনিম্ন উইথড্র ১০০ টাকা (আপনি চাইলে বদলাতে পারেন)
    if amount < 100:
        flash("সর্বনিম্ন উত্তোলনের পরিমাণ ১০০ টাকা!", "warning")
    elif user['balance'] >= amount:
        # ব্যালেন্স কাটা হচ্ছে
        new_balance = user['balance'] - amount
        supabase.table("users").update({"balance": new_balance}).eq("id", user_id).execute()
        
        # ডাটাবেসে রিকোয়েস্ট সেভ করা হচ্ছে
        supabase.table("withdrawals").insert({
            "user_id": user_id,
            "method": method,
            "account_number": account_number,
            "amount": amount,
            "status": "Pending" # এডমিন এপ্রুভ করার আগ পর্যন্ত Pending থাকবে
        }).execute()
        
        flash("উত্তোলন রিকোয়েস্ট সফলভাবে পাঠানো হয়েছে! এডমিন খুব দ্রুত পেমেন্ট করে দেবে।", "success")
    else:
        flash("আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই!", "danger")
        
    return redirect(url_for('dashboard'))
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data and check_password_hash(res.data[0]['password_hash'], password):
            session['user_id'] = res.data[0]['id']
            return redirect(url_for('dashboard'))
        flash("Invalid Credentials", "danger")
    return render_template('login.html')
    
@app.route('/claim_free', methods=['POST'])
def claim_free():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    # Check 8 hours condition
    pkg = supabase.table("user_packages").select("*").eq("user_id", user_id).eq("package_name", "FREE").execute()
    if pkg.data:
        last_claim = datetime.fromisoformat(pkg.data[0]['last_claim_time'].split('.')[0])
        if datetime.now() >= last_claim + timedelta(hours=8):
            # Update balance (+7 Taka)
            user = supabase.table("users").select("balance").eq("id", user_id).execute().data[0]
            new_balance = user['balance'] + 7
            
            supabase.table("users").update({"balance": new_balance}).eq("id", user_id).execute()
            supabase.table("user_packages").update({"last_claim_time": datetime.now().isoformat()}).eq("id", pkg.data[0]['id']).execute()
            
            flash("Successfully claimed 7 BDT!", "success")
        else:
            flash("You can claim every 8 hours.", "warning")
            
    return redirect(url_for('dashboard'))

@app.route('/buy_vip/<pkg_name>', methods=['POST'])
def buy_vip(pkg_name):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    pkg_price = VIP_PACKAGES[pkg_name]['price']
    
    if user['balance'] >= pkg_price:
        # Deduct balance and add VIP
        supabase.table("users").update({"balance": user['balance'] - pkg_price, "is_vip": True}).eq("id", user_id).execute()
        supabase.table("user_packages").insert({"user_id": user_id, "package_name": pkg_name, "last_claim_time": datetime.now().isoformat()}).execute()
        
        # --- REFERRAL LOGIC (50 TK + 2% Commition) ---
        if not user['is_vip'] and user['referred_by']:
            referrer_res = supabase.table("users").select("*").eq("referral_code", user['referred_by']).execute()
            if referrer_res.data:
                referrer = referrer_res.data[0]
                bonus = 50 + (pkg_price * 0.02)
                supabase.table("users").update({
                    "balance": referrer['balance'] + bonus,
                    "total_referrals": referrer['total_referrals'] + 1,
                    "total_earned": referrer['total_earned'] + bonus
                }).eq("id", referrer['id']).execute()
                
        flash(f"Successfully purchased {pkg_name}!", "success")
    else:
        flash("Insufficient Balance. Please deposit.", "danger")
        
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
