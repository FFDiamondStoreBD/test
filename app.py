import os
import uuid
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "8a5f9c2d4e1b6a7f8d9c0e3b2a1f4c7d")
app.permanent_session_lifetime = timedelta(days=30)

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

VIP_PACKAGES = {
    "VIP_1": {"price": 500, "daily_profit": 50, "mead_days": 30},
    "VIP_2": {"price": 1000, "daily_profit": 110, "mead_days": 30},
    "VIP_3": {"price": 2000, "daily_profit": 230, "mead_days": 30},
    "VIP_4": {"price": 5000, "daily_profit": 600, "mead_days": 30},
    "VIP_5": {"price": 10000, "daily_profit": 1300, "mead_days": 30},
}

def is_admin():
    if 'user_id' not in session: return False
    user = supabase.table("users").select("is_admin").eq("id", session['user_id']).execute()
    return user.data and user.data[0].get('is_admin')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        phone = request.form['phone']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        referred_by = request.form.get('referral_code', '')
        fingerprint = request.form.get('fingerprint', '') 
        my_ref_code = str(uuid.uuid4())[:8].upper()

        if not fingerprint:
            flash("ডিভাইস আইডেন্টিফাই করা যাচ্ছে না! দয়া করে পেজটি রিলোড দিন।", "danger")
            return redirect(url_for('register'))

        existing_user = supabase.table("users").select("id").eq("email", email).execute()
        if existing_user.data:
            flash("এই ইমেইল দিয়ে ইতিমধ্যেই একটি একাউন্ট খোলা আছে!", "danger")
            return redirect(url_for('register'))

        existing_device = supabase.table("users").select("id").eq("device_fingerprint", fingerprint).execute()
        if existing_device.data:
            flash("দুঃখিত! এক ডিভাইস থেকে শুধুমাত্র একটি একাউন্টই খোলা যাবে। আপনি লগিন করুন।", "danger")
            return redirect(url_for('login'))

        initial_balance = 0.0
        if referred_by:
            referrer_check = supabase.table("users").select("id").eq("referral_code", referred_by).execute()
            if referrer_check.data:
                initial_balance = 50.0  
            else:
                referred_by = '' 

        try:
            user_data = {
                "name": name, "phone": phone, "email": email, "password_hash": password, 
                "referral_code": my_ref_code, "referred_by": referred_by,
                "device_fingerprint": fingerprint, "balance": initial_balance 
            }
            res = supabase.table("users").insert(user_data).execute()
            if res.data:
                supabase.table("user_packages").insert({"user_id": res.data[0]['id'], "package_name": "FREE", "last_claim_time": "2000-01-01T00:00:00"}).execute()
                if initial_balance > 0:
                    flash("রেফারেল কোড ব্যবহারের জন্য আপনি ৫০ টাকা ফ্রি বোনাস পেয়েছেন! লগিন করুন।", "success")
                else:
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
            if res.data[0].get('is_banned'):
                flash("আপনার একাউন্টটি ব্যান করা হয়েছে!", "danger")
                return redirect(url_for('login'))
            session.permanent = True
            session['user_id'] = res.data[0]['id']
            return redirect(url_for('dashboard'))
        flash("ইমেইল বা পাসওয়ার্ড ভুল হয়েছে!", "danger")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("লগআউট সফল হয়েছে।", "success")
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    notice_res = supabase.table("settings").select("notice_text").eq("id", 1).execute()
    notice = notice_res.data[0]['notice_text'] if notice_res.data else "InvestEarn এ স্বাগতম!"

    pkg_res = supabase.table("user_packages").select("*").eq("user_id", session['user_id']).execute()
    packages = pkg_res.data
    
    for p in packages:
        clean_time = p['last_claim_time'].split('.')[0].split('+')[0]
        last_claim = datetime.fromisoformat(clean_time)
        if p['package_name'] == 'FREE':
            p['next_claim'] = (last_claim + timedelta(hours=8)).isoformat() + "Z"
            p['reward'] = 7
            p['interval'] = '৮ ঘণ্টা'
        elif p['package_name'] in VIP_PACKAGES:
            p['next_claim'] = (last_claim + timedelta(hours=24)).isoformat() + "Z"
            p['reward'] = VIP_PACKAGES[p['package_name']]['daily_profit']
            p['interval'] = '২৪ ঘণ্টা'

    return render_template('dashboard.html', user=user, packages=packages, vip=VIP_PACKAGES, notice=notice)

@app.route('/buy_premium_offer', methods=['POST'])
def buy_premium_offer():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    
    dep_res = supabase.table("deposits").select("amount").eq("user_id", user_id).eq("status", "Approved").execute()
    total_dep = sum(d['amount'] for d in dep_res.data)
    
    if total_dep < 100:
        flash("এই অফারটি নিতে হলে আপনাকে প্রথমে ন্যূনতম ১০০ টাকা Add Money (ডিপোজিট) করতে হবে!", "danger")
        return redirect(url_for('transfer'))
        
    if user['balance'] < 100:
        flash("আপনার ব্যালেন্স ১০০ টাকার নিচে!", "danger")
        return redirect(url_for('transfer'))
        
    supabase.table("users").update({
        "balance": user['balance'] - 100, "has_premium_offer": True, "is_vip": True
    }).eq("id", user_id).execute()
    supabase.table("user_packages").insert({"user_id": user_id, "package_name": "VIP_1", "last_claim_time": datetime.now().isoformat()}).execute()
    
    flash("অভিনন্দন! স্পেশাল প্রিমিয়াম অফারটি সফলভাবে কেনা হয়েছে।", "success")
    return redirect(url_for('dashboard'))

@app.route('/claim/<int:pkg_id>', methods=['POST'])
def claim_reward(pkg_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    pkg_res = supabase.table("user_packages").select("*").eq("id", pkg_id).eq("user_id", user_id).execute()
    if not pkg_res.data: return redirect(url_for('dashboard'))
        
    pkg = pkg_res.data[0]
    pkg_name = pkg['package_name']
    reward, interval_hours = (7, 8) if pkg_name == "FREE" else (VIP_PACKAGES[pkg_name]['daily_profit'], 24)
        
    clean_time = pkg['last_claim_time'].split('.')[0].split('+')[0]
    if datetime.now() >= datetime.fromisoformat(clean_time) + timedelta(hours=interval_hours):
        user = supabase.table("users").select("balance").eq("id", user_id).execute().data[0]
        supabase.table("users").update({"balance": user['balance'] + reward}).eq("id", user_id).execute()
        supabase.table("user_packages").update({"last_claim_time": datetime.now().isoformat()}).eq("id", pkg_id).execute()
        flash(f"আপনি সফলভাবে ৳{reward} ক্লেইম করেছেন!", "success")
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
        flash(f"আপনি সফলভাবে {pkg_name} কিনেছেন!", "success")
    else:
        flash("আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই।", "danger")
    return redirect(url_for('dashboard'))

@app.route('/transfer')
def transfer():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    return render_template('transfer.html', user=user)

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'user_id' not in session: return redirect(url_for('login'))
    amount = float(request.form.get('amount'))
    if amount < 50:
        flash("সর্বনিম্ন ডিপোজিট ৫০ টাকা!", "warning")
    else:
        supabase.table("deposits").insert({
            "user_id": session['user_id'], "method": request.form.get('method'), "sender_number": request.form.get('sender_number'),
            "transaction_id": request.form.get('transaction_id'), "amount": amount, "status": "Pending"
        }).execute()
        flash("ডিপোজিট রিকোয়েস্ট পাঠানো হয়েছে!", "success")
    return redirect(url_for('transfer'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    amount = float(request.form.get('amount'))
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    
    min_withdraw = 100 if user.get('has_premium_offer') else 500
    
    if amount < min_withdraw:
        flash(f"আপনার বর্তমান প্যাকেজ অনুযায়ী সর্বনিম্ন উত্তোলনের পরিমাণ {min_withdraw} টাকা!", "warning")
        return redirect(url_for('transfer'))
        
    if not user.get('is_vip') and not user.get('has_premium_offer'):
        dep_res = supabase.table("deposits").select("amount").eq("user_id", user_id).eq("status", "Approved").execute()
        total_dep = sum(d['amount'] for d in dep_res.data)
        if total_dep < 70:
            flash("Suspicious Activity Detected! ভেরিফিকেশনের জন্য এড মানি অপশন থেকে ন্যূনতম ৭০ টাকা ডিপোজিট করুন।", "danger")
            return redirect(url_for('transfer'))
            
    if user['balance'] >= amount:
        supabase.table("users").update({"balance": user['balance'] - amount}).eq("id", user_id).execute()
        supabase.table("withdrawals").insert({"user_id": user_id, "method": request.form.get('method'), "account_number": request.form.get('account_number'), "amount": amount, "status": "Pending"}).execute()
        flash("উত্তোলন রিকোয়েস্ট পাঠানো হয়েছে!", "success")
    else:
        flash("আপনার একাউন্টে পর্যাপ্ত ব্যালেন্স নেই!", "danger")
    return redirect(url_for('transfer'))

# --- HIDDEN LEADERSHIP ROUTES ---
@app.route('/leadership')
def leadership():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    team_res = supabase.table("users").select("id, name, email, created_at").eq("referred_by", user['referral_code']).order("created_at", desc=True).execute()
    team = team_res.data
    
    if team:
        team_ids = [m['id'] for m in team]
        dep_res = supabase.table("deposits").select("user_id, amount").in_("user_id", team_ids).eq("status", "Approved").execute()
        dep_dict = {}
        for d in dep_res.data:
            dep_dict[d['user_id']] = dep_dict.get(d['user_id'], 0) + d['amount']
        for m in team:
            m['total_deposited'] = dep_dict.get(m['id'], 0.0)
            
    leader_w_res = supabase.table("withdrawals").select("*").eq("user_id", user['id']).ilike("method", "Leader%").order("created_at", desc=True).execute()
    return render_template('leadership.html', user=user, team=team, leader_withdraws=leader_w_res.data)

@app.route('/leader_withdraw', methods=['POST'])
def leader_withdraw():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    amount = float(request.form.get('amount'))
    method = "Leader - " + request.form.get('method')
    account_number = request.form.get('account_number')
    
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    current_leader_balance = user.get('leader_balance') or 0.0
    
    if amount < 100:
        flash("সর্বনিম্ন উত্তোলনের পরিমাণ ১০০ টাকা!", "warning")
    elif current_leader_balance >= amount:
        supabase.table("users").update({"leader_balance": current_leader_balance - amount}).eq("id", user_id).execute()
        supabase.table("withdrawals").insert({"user_id": user_id, "method": method, "account_number": account_number, "amount": amount, "status": "Pending"}).execute()
        flash("লিডারশিপ ব্যালেন্স থেকে উত্তোলন রিকোয়েস্ট পাঠানো হয়েছে!", "success")
    else:
        flash("আপনার লিডারশিপ ব্যালেন্সে পর্যাপ্ত টাকা নেই!", "danger")
    return redirect(url_for('leadership'))

# ==========================================
#         ADMIN PANEL ROUTES
# ==========================================

@app.route('/admin')
def admin_panel():
    if not is_admin(): return redirect(url_for('dashboard'))
    
    all_users = supabase.table("users").select("id").execute().data
    total_users = len(all_users)
    
    deposits = supabase.table("deposits").select("*").order("created_at", desc=True).execute().data
    
    notice_data = supabase.table("settings").select("notice_text").eq("id", 1).execute().data
    current_notice = notice_data[0]['notice_text'] if notice_data else ""
    
    users = supabase.table("users").select("id, name, email").execute().data
    user_dict = {u['id']: u for u in users}
    for d in deposits: 
        d['user_name'] = user_dict.get(d['user_id'], {}).get('name', 'Unknown')
        d['user_email'] = user_dict.get(d['user_id'], {}).get('email', 'Unknown')
        
    return render_template('admin.html', total_users=total_users, deposits=deposits, current_notice=current_notice)

@app.route('/admin/users')
def admin_users():
    if not is_admin(): return redirect(url_for('dashboard'))
    users = supabase.table("users").select("*").order("id", desc=True).execute().data
    return render_template('admin_users.html', users=users)

@app.route('/admin/withdrawals')
def admin_withdrawals():
    if not is_admin(): return redirect(url_for('dashboard'))
    withdrawals = supabase.table("withdrawals").select("*").order("created_at", desc=True).execute().data
    
    users = supabase.table("users").select("id, name, email").execute().data
    user_dict = {u['id']: u for u in users}
    for w in withdrawals: 
        w['user_name'] = user_dict.get(w['user_id'], {}).get('name', 'Unknown')
        w['user_email'] = user_dict.get(w['user_id'], {}).get('email', 'Unknown')
        
    return render_template('admin_withdrawals.html', withdrawals=withdrawals)

@app.route('/admin/update_notice', methods=['POST'])
def admin_update_notice():
    if not is_admin(): return redirect(url_for('dashboard'))
    new_notice = request.form.get('notice')
    check = supabase.table("settings").select("*").eq("id", 1).execute()
    if check.data:
        supabase.table("settings").update({"notice_text": new_notice}).eq("id", 1).execute()
    else:
        supabase.table("settings").insert({"id": 1, "notice_text": new_notice}).execute()
    flash("নোটিশ সফলভাবে আপডেট করা হয়েছে!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/deposit/<int:d_id>/<action>')
def admin_handle_deposit(d_id, action):
    if not is_admin(): return redirect(url_for('dashboard'))
    d_data = supabase.table("deposits").select("*").eq("id", d_id).execute().data[0]
    if d_data['status'] == 'Pending':
        if action == 'approve':
            u_data = supabase.table("users").select("*").eq("id", d_data['user_id']).execute().data[0]
            supabase.table("users").update({"balance": u_data['balance'] + d_data['amount']}).eq("id", d_data['user_id']).execute()
            
            # Leadership Bonus 50%
            if u_data.get('referred_by'):
                referrer_res = supabase.table("users").select("*").eq("referral_code", u_data['referred_by']).execute()
                if referrer_res.data:
                    referrer = referrer_res.data[0]
                    leader_bonus = d_data['amount'] * 0.50
                    current_leader_balance = referrer.get('leader_balance') or 0.0
                    supabase.table("users").update({"leader_balance": current_leader_balance + leader_bonus}).eq("id", referrer['id']).execute()
            
            supabase.table("deposits").update({"status": "Approved"}).eq("id", d_id).execute()
            flash("ডিপোজিট এপ্রুভ করা হয়েছে!", "success")
        elif action == 'reject':
            supabase.table("deposits").update({"status": "Rejected"}).eq("id", d_id).execute()
            flash("ডিপোজিট বাতিল করা হয়েছে!", "warning")
    return redirect(url_for('admin_panel'))

@app.route('/admin/withdraw/<int:w_id>/<action>')
def admin_handle_withdraw(w_id, action):
    if not is_admin(): return redirect(url_for('dashboard'))
    w_data = supabase.table("withdrawals").select("*").eq("id", w_id).execute().data[0]
    if action == 'approve':
        supabase.table("withdrawals").update({"status": "Approved"}).eq("id", w_id).execute()
        flash("উত্তোলন এপ্রুভ করা হয়েছে!", "success")
    elif action == 'reject' and w_data['status'] == 'Pending':
        u_data = supabase.table("users").select("*").eq("id", w_data['user_id']).execute().data[0]
        
        # Check if normal or leader withdraw
        if w_data['method'].startswith("Leader"):
            current_leader = u_data.get('leader_balance') or 0.0
            supabase.table("users").update({"leader_balance": current_leader + w_data['amount']}).eq("id", w_data['user_id']).execute()
        else:
            supabase.table("users").update({"balance": u_data['balance'] + w_data['amount']}).eq("id", w_data['user_id']).execute()
            
        supabase.table("withdrawals").update({"status": "Rejected"}).eq("id", w_id).execute()
        flash("উত্তোলন বাতিল করা হয়েছে এবং টাকা ফেরত দেওয়া হয়েছে!", "warning")
    return redirect(url_for('admin_withdrawals'))

@app.route('/admin/update_balance/<int:user_id>', methods=['POST'])
def admin_update_balance(user_id):
    if is_admin(): supabase.table("users").update({"balance": float(request.form.get('balance'))}).eq("id", user_id).execute()
    flash("ব্যালেন্স আপডেট হয়েছে!", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/toggle_ban/<int:user_id>')
def admin_toggle_ban(user_id):
    if is_admin():
        user = supabase.table("users").select("is_banned").eq("id", user_id).execute().data[0]
        supabase.table("users").update({"is_banned": not user.get('is_banned')}).eq("id", user_id).execute()
        flash("ইউজারের স্ট্যাটাস পরিবর্তন হয়েছে!", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/delete_user/<int:user_id>')
def admin_delete_user(user_id):
    if is_admin():
        for t in["user_packages", "withdrawals", "deposits", "users"]: supabase.table(t).delete().eq("user_id" if t!="users" else "id", user_id).execute()
        flash("ইউজারকে ডিলিট করা হয়েছে!", "danger")
    return redirect(url_for('admin_users'))

# --- Other Pages Routes ---
@app.route('/history')
def history():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    withdraw_res = supabase.table("withdrawals").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    deposit_res = supabase.table("deposits").select("*").eq("user_id", session['user_id']).order("created_at", desc=True).execute()
    return render_template('history.html', user=user, withdrawals=withdraw_res.data, deposits=deposit_res.data)

@app.route('/referrals')
def referrals():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    team_res = supabase.table("users").select("name, created_at, is_vip").eq("referred_by", user['referral_code']).order("created_at", desc=True).execute()
    return render_template('referrals.html', user=user, team=team_res.data)

@app.route('/leaderboard')
def leaderboard():
    fake_names =["Rahim", "Karim", "Samiya", "Nusrat", "Arif", "Hasan", "Mehedi", "Tariq", "Fatema", "Rina", "Shakil", "Imran", "Farjana", "Sumaiya", "Tanjim", "Jony", "Momin", "Sujon", "Riaz", "Habib"]
    today_str = datetime.now().strftime('%Y-%m-%d')
    random.seed(today_str)
    
    earners =[{"name": n, "total_earned": random.randint(5000, 50000)} for n in random.sample(fake_names, 20)]
    earners.sort(key=lambda x: x["total_earned"], reverse=True)
    referrers =[{"name": n, "total_referrals": random.randint(50, 500)} for n in random.sample(fake_names, 20)]
    referrers.sort(key=lambda x: x["total_referrals"], reverse=True)
    random.seed()
    return render_template('leaderboard.html', earners=earners, referrers=referrers)

if __name__ == '__main__':
    app.run(debug=True)
