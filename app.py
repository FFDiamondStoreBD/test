import os
import uuid
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "8a5f9c2d4e1b6a7f8d9c0e3b2a1f4c7d")

# Supabase Setup
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("WARNING: SUPABASE_URL or SUPABASE_KEY is missing!")
else:
    supabase: Client = create_client(url, key)

VIP_PACKAGES = {
    "VIP_1": {"price": 500, "daily_profit": 50, "mead_days": 30},
    "VIP_2": {"price": 1000, "daily_profit": 110, "mead_days": 30},
    "VIP_3": {"price": 2000, "daily_profit": 230, "mead_days": 30},
    "VIP_4": {"price": 5000, "daily_profit": 600, "mead_days": 30},
    "VIP_5": {"price": 10000, "daily_profit": 1300, "mead_days": 30},
}

@app.route('/')
def index():
    try:
        top_earners = supabase.table("users").select("name, total_earned").order("total_earned", desc=True).limit(5).execute()
        top_referrers = supabase.table("users").select("name, total_referrals").order("total_referrals", desc=True).limit(5).execute()
        proofs = supabase.table("proofs").select("*").order("created_at", desc=True).limit(10).execute()
        return render_template('index.html', earners=top_earners.data, referrers=top_referrers.data, proofs=proofs.data)
    except Exception as e:
        return f"Database Connection Error: {e}"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        referred_by = request.form.get('referral_code', '')
        my_ref_code = str(uuid.uuid4())[:8].upper()

        existing_user = supabase.table("users").select("id").eq("email", email).execute()
        if existing_user.data:
            flash("এই ইমেইল দিয়ে ইতিমধ্যেই একটি একাউন্ট খোলা আছে!", "danger")
            return redirect(url_for('register'))

        try:
            user_data = {
                "name": name, "phone": phone, "email": email, 
                "password_hash": password, "referral_code": my_ref_code, 
                "referred_by": referred_by
            }
            res = supabase.table("users").insert(user_data).execute()
            if res.data:
                user_id = res.data[0]['id']
                supabase.table("user_packages").insert({
                    "user_id": user_id, "package_name": "FREE", "last_claim_time": "2000-01-01T00:00:00"
                }).execute()
                flash("একাউন্ট সফলভাবে তৈরি হয়েছে! অনুগ্রহ করে লগিন করুন।", "success")
                return redirect(url_for('login'))
        except Exception as e:
            flash("একাউন্ট তৈরি করতে সমস্যা হয়েছে! আবার চেষ্টা করুন।", "danger")
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        res = supabase.table("users").select("*").eq("email", email).execute()
        if res.data and check_password_hash(res.data[0]['password_hash'], password):
            # ব্যান করা ইউজারদের লগিন ব্লক করা হচ্ছে
            if res.data[0].get('is_banned'):
                flash("আপনার একাউন্টটি ব্যান করা হয়েছে! সাপোর্টে যোগাযোগ করুন।", "danger")
                return redirect(url_for('login'))
                
            session['user_id'] = res.data[0]['id']
            return redirect(url_for('dashboard'))
        flash("ইমেইল বা পাসওয়ার্ড ভুল হয়েছে!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("আপনি সফলভাবে লগআউট হয়েছেন।", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    if user.get('is_banned'):
        session.pop('user_id', None)
        flash("আপনার একাউন্ট ব্যান করা হয়েছে।", "danger")
        return redirect(url_for('login'))

    pkg_res = supabase.table("user_packages").select("*").eq("user_id", session['user_id']).execute()
    withdraw_res = supabase.table("withdrawals").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    return render_template('dashboard.html', user=user, packages=pkg_res.data, vip=VIP_PACKAGES, withdrawals=withdraw_res.data)

@app.route('/claim_free', methods=['POST'])
def claim_free():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    pkg = supabase.table("user_packages").select("*").eq("user_id", user_id).eq("package_name", "FREE").execute()
    if pkg.data:
        last_claim = datetime.fromisoformat(pkg.data[0]['last_claim_time'].split('.')[0])
        if datetime.now() >= last_claim + timedelta(hours=8):
            user = supabase.table("users").select("balance").eq("id", user_id).execute().data[0]
            new_balance = user['balance'] + 7
            supabase.table("users").update({"balance": new_balance}).eq("id", user_id).execute()
            supabase.table("user_packages").update({"last_claim_time": datetime.now().isoformat()}).eq("id", pkg.data[0]['id']).execute()
            flash("আপনি সফলভাবে ৭ টাকা ক্লেইম করেছেন!", "success")
        else:
            flash("আপনি প্রতি ৮ ঘন্টা পর পর ক্লেইম করতে পারবেন।", "warning")
    return redirect(url_for('dashboard'))

@app.route('/buy_vip/<pkg_name>', methods=['POST'])
def buy_vip(pkg_name):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    pkg_price = VIP_PACKAGES[pkg_name]['price']
    
    if user['balance'] >= pkg_price:
        supabase.table("users").update({"balance": user['balance'] - pkg_price, "is_vip": True}).eq("id", user_id).execute()
        supabase.table("user_packages").insert({"user_id": user_id, "package_name": pkg_name, "last_claim_time": datetime.now().isoformat()}).execute()
        flash(f"আপনি সফলভাবে {pkg_name} প্যাকেজটি কিনেছেন!", "success")
    else:
        flash("আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই।", "danger")
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    method = request.form.get('method')
    account_number = request.form.get('account_number')
    amount = float(request.form.get('amount'))
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    
    if amount < 100:
        flash("সর্বনিম্ন উত্তোলনের পরিমাণ ১০০ টাকা!", "warning")
    elif user['balance'] >= amount:
        new_balance = user['balance'] - amount
        supabase.table("users").update({"balance": new_balance}).eq("id", user_id).execute()
        
        # Referral Bonus on FIRST withdraw
        existing_withdrawals = supabase.table("withdrawals").select("id").eq("user_id", user_id).execute()
        if len(existing_withdrawals.data) == 0 and user['referred_by']:
            referrer_res = supabase.table("users").select("*").eq("referral_code", user['referred_by']).execute()
            if referrer_res.data:
                referrer = referrer_res.data[0]
                bonus = 50 + (amount * 0.02)
                supabase.table("users").update({
                    "balance": referrer['balance'] + bonus,
                    "total_referrals": referrer['total_referrals'] + 1,
                    "total_earned": referrer['total_earned'] + bonus
                }).eq("id", referrer['id']).execute()
        
        supabase.table("withdrawals").insert({"user_id": user_id, "method": method, "account_number": account_number, "amount": amount, "status": "Pending"}).execute()
        flash("উত্তোলন রিকোয়েস্ট সফলভাবে পাঠানো হয়েছে!", "success")
    else:
        flash("আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই!", "danger")
    return redirect(url_for('dashboard'))

# ==========================================
#         ADMIN PANEL ROUTES (NEW)
# ==========================================

# Check if current user is admin
def is_admin():
    if 'user_id' not in session: return False
    user = supabase.table("users").select("is_admin").eq("id", session['user_id']).execute()
    return user.data and user.data[0].get('is_admin')

@app.route('/admin')
def admin_panel():
    if not is_admin():
        flash("এই পেজে প্রবেশের অনুমতি আপনার নেই!", "danger")
        return redirect(url_for('dashboard'))
    
    # Fetching all users
    users = supabase.table("users").select("*").order("id", desc=True).execute().data
    
    # Fetching withdrawals and mapping user data manually to avoid join issues
    withdrawals = supabase.table("withdrawals").select("*").order("created_at", desc=True).execute().data
    user_dict = {u['id']: u for u in users}
    
    for w in withdrawals:
        w['user_name'] = user_dict.get(w['user_id'], {}).get('name', 'Unknown')
        w['user_email'] = user_dict.get(w['user_id'], {}).get('email', 'Unknown')
        
    return render_template('admin.html', users=users, withdrawals=withdrawals)

@app.route('/admin/update_balance/<int:user_id>', methods=['POST'])
def admin_update_balance(user_id):
    if not is_admin(): return redirect(url_for('dashboard'))
    new_balance = float(request.form.get('balance'))
    supabase.table("users").update({"balance": new_balance}).eq("id", user_id).execute()
    flash("ব্যালেন্স সফলভাবে আপডেট করা হয়েছে!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/toggle_ban/<int:user_id>')
def admin_toggle_ban(user_id):
    if not is_admin(): return redirect(url_for('dashboard'))
    user = supabase.table("users").select("is_banned").eq("id", user_id).execute().data[0]
    new_status = not user.get('is_banned')
    supabase.table("users").update({"is_banned": new_status}).eq("id", user_id).execute()
    flash("ইউজারের একাউন্ট স্ট্যাটাস পরিবর্তন করা হয়েছে!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:user_id>')
def admin_delete_user(user_id):
    if not is_admin(): return redirect(url_for('dashboard'))
    # আগে রিলেটেড ডাটা ডিলিট করতে হবে (Foreign Key এর কারণে)
    supabase.table("user_packages").delete().eq("user_id", user_id).execute()
    supabase.table("withdrawals").delete().eq("user_id", user_id).execute()
    supabase.table("users").delete().eq("id", user_id).execute()
    flash("ইউজারকে সফলভাবে ডিলিট করা হয়েছে!", "danger")
    return redirect(url_for('admin_panel'))

@app.route('/admin/withdraw/<int:w_id>/<action>')
def admin_handle_withdraw(w_id, action):
    if not is_admin(): return redirect(url_for('dashboard'))
    
    w_data = supabase.table("withdrawals").select("*").eq("id", w_id).execute().data[0]
    
    if action == 'approve':
        supabase.table("withdrawals").update({"status": "Approved"}).eq("id", w_id).execute()
        flash("উত্তোলন এপ্রুভ করা হয়েছে!", "success")
        
    elif action == 'reject':
        if w_data['status'] == 'Pending':
            # রিজেক্ট করলে ইউজারের ব্যালেন্সে টাকা ফেরত দেওয়া হচ্ছে
            u_data = supabase.table("users").select("balance").eq("id", w_data['user_id']).execute().data[0]
            supabase.table("users").update({"balance": u_data['balance'] + w_data['amount']}).eq("id", w_data['user_id']).execute()
        supabase.table("withdrawals").update({"status": "Rejected"}).eq("id", w_id).execute()
        flash("উত্তোলন বাতিল করা হয়েছে এবং টাকা ফেরত দেওয়া হয়েছে!", "warning")
        
    return redirect(url_for('admin_panel'))

# History and Referrals Routes
@app.route('/history')
def history():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    withdraw_res = supabase.table("withdrawals").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    return render_template('history.html', user=user, withdrawals=withdraw_res.data)

@app.route('/referrals')
def referrals():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    team_res = supabase.table("users").select("name, created_at, is_vip").eq("referred_by", user['referral_code']).order("created_at", desc=True).execute()
    return render_template('referrals.html', user=user, team=team_res.data)

if __name__ == '__main__':
    app.run(debug=True)
