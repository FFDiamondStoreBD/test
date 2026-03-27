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
    "VIP_1": {"price": 300, "daily_profit": 40, "mead_days": 30},
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
                "device_fingerprint": fingerprint, "balance": initial_balance, "total_earned": initial_balance 
            }
            res = supabase.table("users").insert(user_data).execute()
            if res.data:
                supabase.table("user_packages").insert({"user_id": res.data[0]['id'], "package_name": "FREE", "last_claim_time": "2000-01-01T00:00:00"}).execute()
                if initial_balance > 0:
                    flash("রেফারেল কোড ব্যবহারের জন্য আপনি ৫০ টাকা ফ্রি বোনাস পেয়েছেন!", "success")
                else:
                    flash("একাউন্ট সফলভাবে তৈরি হয়েছে! অনুগ্রহ করে লগিন করুন।", "success")
                return redirect(url_for('login'))
        except Exception as e:
            flash("একাউন্ট তৈরি করতে সমস্যা হয়েছে! আবার চেষ্টা করুন।", "danger")
            return redirect(url_for('register'))
            
    ref_code = request.args.get('ref', '')
    return render_template('register.html', ref_code=ref_code)

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
    notice = notice_res.data[0]['notice_text'] if notice_res.data else "Easy Earn এ স্বাগতম!"

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
        user = supabase.table("users").select("balance, total_earned").eq("id", user_id).execute().data[0]
        supabase.table("users").update({"balance": user['balance'] + reward, "total_earned": user.get('total_earned', 0.0) + reward}).eq("id", user_id).execute()
        supabase.table("user_packages").update({"last_claim_time": datetime.now().isoformat()}).eq("id", pkg_id).execute()
        flash(f"আপনি সফলভাবে ৳{reward} ক্লেইম করেছেন!", "success")
    else:
        flash("এখনো ক্লেইম করার সময় হয়নি!", "warning")
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


# ==========================================
#         LEADERSHIP APPLY SYSTEM
# ==========================================
@app.route('/apply_leader', methods=['GET', 'POST'])
def apply_leader():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    if user.get('is_leader'):
        return redirect(url_for('leadership'))
        
    app_res = supabase.table("leadership_applications").select("*").eq("user_id", user['id']).order("created_at", desc=True).execute()
    is_pending = True if app_res.data and app_res.data[0]['status'] == 'Pending' else False
    
    if request.method == 'POST':
        data = {
            "user_id": user['id'],
            "name": request.form.get('name'),
            "email": request.form.get('email'),
            "phone": request.form.get('phone'),
            "telegram_username": request.form.get('telegram_username'), # <-- NEW: Telegram Username
            "age": int(request.form.get('age')),
            "gender": request.form.get('gender'),
            "education": request.form.get('education'),
            "address": request.form.get('address'),
            "photo_url": request.form.get('photo_url'),
            "status": "Pending"
        }
        supabase.table("leadership_applications").insert(data).execute()
        flash("আপনার লিডারশিপ আবেদনটি সফলভাবে জমা হয়েছে! এডমিন খুব দ্রুত এটি রিভিউ করবেন।", "success")
        return redirect(url_for('apply_leader'))
        
    return render_template('apply_leader.html', user=user, pending=is_pending)
@app.route('/leadership')
def leadership():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    # Check if user is actually approved leader
    if not user.get('is_leader'):
        flash("আপনাকে প্রথমে লিডারশিপের জন্য আবেদন করতে হবে!", "warning")
        return redirect(url_for('apply_leader'))
    
    team_res = supabase.table("users").select("id, name, email, created_at").eq("referred_by", user['referral_code']).order("created_at", desc=True).execute()
    team = team_res.data
    
    if team:
        team_ids =[m['id'] for m in team]
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
    withdrawals = supabase.table("withdrawals").select("*").eq("status", "Pending").order("created_at", desc=True).execute().data
    users = supabase.table("users").select("id, name, email").execute().data
    user_dict = {u['id']: u for u in users}
    for w in withdrawals: 
        w['user_name'] = user_dict.get(w['user_id'], {}).get('name', 'Unknown')
        w['user_email'] = user_dict.get(w['user_id'], {}).get('email', 'Unknown')
    return render_template('admin_withdrawals.html', withdrawals=withdrawals)

@app.route('/admin/leadership_apps')
def admin_leadership_apps():
    if not is_admin(): return redirect(url_for('dashboard'))
    apps = supabase.table("leadership_applications").select("*").order("created_at", desc=True).execute().data
    return render_template('admin_leadership.html', applications=apps)

@app.route('/admin/leadership_action/<int:app_id>/<action>')
def admin_handle_leadership(app_id, action):
    if not is_admin(): return redirect(url_for('dashboard'))
    app_data = supabase.table("leadership_applications").select("*").eq("id", app_id).execute().data[0]
    
    if action == 'approve':
        supabase.table("leadership_applications").update({"status": "Approved"}).eq("id", app_id).execute()
        supabase.table("users").update({"is_leader": True}).eq("id", app_data['user_id']).execute()
        flash("লিডারশিপ রিকোয়েস্ট এপ্রুভ করা হয়েছে!", "success")
    elif action == 'reject':
        supabase.table("leadership_applications").update({"status": "Rejected"}).eq("id", app_id).execute()
        flash("রিকোয়েস্ট বাতিল করা হয়েছে!", "warning")
    return redirect(url_for('admin_leadership_apps'))

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
            
            # --- 50% Leadership Bonus Logic ---
            if u_data.get('referred_by'):
                referrer_res = supabase.table("users").select("*").eq("referral_code", u_data['referred_by']).execute()
                if referrer_res.data:
                    referrer = referrer_res.data[0]
                    # বোনাস শুধুমাত্র এপ্রুভড লিডাররা পাবে
                    if referrer.get('is_leader'):
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
    withdrawals = withdraw_res.data
    total_withdraw = sum(w['amount'] for w in withdrawals if w['status'] == 'Approved')
    return render_template('history.html', user=user, withdrawals=withdrawals, total_withdraw=total_withdraw)

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

# ==========================================
#         NEW: PWA AND SPIN ROUTES
# ==========================================
@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def serve_sw():
    return app.send_static_file('sw.js')

@app.route('/spin')
def spin_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = supabase.table("users").select("*").eq("id", session['user_id']).execute().data[0]
    
    # 24 Hours Time Check
    last_spin = user.get('last_spin_time', '2000-01-01T00:00:00')
    clean_time = last_spin.split('.')[0].split('+')[0]
    next_spin_time = (datetime.fromisoformat(clean_time) + timedelta(hours=24)).isoformat() + "Z"
    
    return render_template('spin.html', user=user, next_spin_time=next_spin_time)

# --- UPDATED: Spin Reward API (With 0.5% chance for 50 TK) ---
@app.route('/api/spin_reward', methods=['POST'])
def api_spin_reward():
    if 'user_id' not in session: return {"error": "Unauthorized"}, 401
    user_id = session['user_id']
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    
    last_spin = user.get('last_spin_time', '2000-01-01T00:00:00')
    clean_time = last_spin.split('.')[0].split('+')[0]
    
    if datetime.now() < datetime.fromisoformat(clean_time) + timedelta(hours=24):
        return {"error": "আপনি ইতিমধ্যেই স্পিন করেছেন! কাল আবার চেষ্টা করুন।"}, 400
        
    # চাকার ৮টি স্লট এবং তাদের পাওয়ার সম্ভাবনা (Probability %)
    slots =[
        {"amount": 0,  "prob": 15.0},   # Slot 0: 0 TK (15%)
        {"amount": 1,  "prob": 25.0},   # Slot 1: 1 TK (25%)
        {"amount": 2,  "prob": 20.0},   # Slot 2: 2 TK (20%)
        {"amount": 5,  "prob": 15.0},   # Slot 3: 5 TK (15%)
        {"amount": 0,  "prob": 15.0},   # Slot 4: 0 TK (15%)
        {"amount": 3,  "prob": 5.0},    # Slot 5: 3 TK (5%)
        {"amount": 10, "prob": 4.5},    # Slot 6: 10 TK (4.5%)
        {"amount": 50, "prob": 0.5},    # Slot 7: 50 TK (Exactly 0.5% chance)
    ]
    
    # ০ থেকে ১০০ এর মধ্যে একটি র‍্যান্ডম নাম্বার তৈরি
    rand_val = random.uniform(0, 100)
    cumulative = 0
    won_index = 0
    
    # কোন স্লটে পড়বে তা হিসাব করা হচ্ছে
    for i, s in enumerate(slots):
        cumulative += s["prob"]
        if rand_val <= cumulative:
            won_index = i
            break
            
    won_amount = slots[won_index]["amount"]
    
    # ব্যালেন্স এবং ডাটাবেস আপডেট
    new_balance = user['balance'] + won_amount
    new_total = user.get('total_earned', 0) + won_amount
    
    supabase.table("users").update({
        "balance": new_balance, 
        "total_earned": new_total,
        "last_spin_time": datetime.now().isoformat()
    }).eq("id", user_id).execute()
    
    # রেজাল্ট পাঠানো হচ্ছে (যেটি দিয়ে ফ্রন্টএন্ড চাকা ঘুরাবে)
    return {
        "reward": won_amount, 
        "slot_index": won_index, # কোন স্লটে থেমেছে তার ইনডেক্স (০ থেকে ৭)
        "message": f"অভিনন্দন! আপনি স্পিন করে ৳{won_amount} জিতেছেন!" if won_amount > 0 else "দুঃখিত! আপনি এবার কিছু পাননি। কাল আবার চেষ্টা করুন!"
        }

# ==========================================
#         GMAIL MICRO-TASKS SYSTEM
# ==========================================

# ১ ঘণ্টার মধ্যে কাজ না করলে ২০ টাকা কাটার ফাংশন
def check_gmail_penalties(user_id):
    overdue_tasks = supabase.table("gmail_tasks").select("*").eq("assigned_user_id", user_id).eq("status", "In Progress").execute().data
    if not overdue_tasks: return
    
    user_data = supabase.table("users").select("balance").eq("id", user_id).execute().data[0]
    current_balance = user_data['balance']
    penalty_applied = False
    
    for task in overdue_tasks:
        if task['assigned_at']:
            clean_time = task['assigned_at'].split('.')[0].split('+')[0]
            assigned_time = datetime.fromisoformat(clean_time)
            
            # যদি ১ ঘন্টা পার হয়ে যায়
            if datetime.now() > assigned_time + timedelta(hours=1):
                current_balance -= 20.0
                penalty_applied = True
                
                # কাজটিকে আবার Available করে দেওয়া হচ্ছে
                supabase.table("gmail_tasks").update({
                    "status": "Available",
                    "assigned_user_id": None,
                    "assigned_at": None
                }).eq("id", task['id']).execute()
                
    if penalty_applied:
        supabase.table("users").update({"balance": current_balance}).eq("id", user_id).execute()
        flash("সতর্কতা: আপনি ১ ঘণ্টার মধ্যে জিমেইল একাউন্ট সাবমিট না করায় আপনার ব্যালেন্স থেকে ২০ টাকা জরিমানা কাটা হয়েছে!", "danger")

@app.route('/gmail_tasks')
def gmail_tasks():
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    user = supabase.table("users").select("*").eq("id", user_id).execute().data[0]
    
    # পেজে ঢোকার সাথে সাথেই চেক করবে জরিমানা খাবে কি না
    check_gmail_penalties(user_id)
    
    # ইউজারের নেওয়া রানিং কাজ
    my_tasks = supabase.table("gmail_tasks").select("*").eq("assigned_user_id", user_id).in_("status", ["In Progress", "Submitted"]).execute().data
    # খালি কাজগুলো (যেগুলো কেউ নেয়নি)
    available_tasks = supabase.table("gmail_tasks").select("*").eq("status", "Available").execute().data
    
    return render_template('gmail_tasks.html', user=user, my_tasks=my_tasks, available_tasks=available_tasks)

@app.route('/take_gmail_task/<int:task_id>', methods=['POST'])
def take_gmail_task(task_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    user_id = session['user_id']
    
    task = supabase.table("gmail_tasks").select("*").eq("id", task_id).execute().data[0]
    if task['status'] == 'Available':
        supabase.table("gmail_tasks").update({
            "status": "In Progress",
            "assigned_user_id": user_id,
            "assigned_at": datetime.now().isoformat()
        }).eq("id", task_id).execute()
        flash("কাজটি আপনি সফলভাবে গ্রহণ করেছেন! ১ ঘণ্টার মধ্যে সম্পন্ন করে সাবমিট করুন।", "success")
    else:
        flash("দুঃখিত, এই কাজটি অন্য কেউ নিয়ে নিয়েছে!", "warning")
    return redirect(url_for('gmail_tasks'))

@app.route('/submit_gmail_task/<int:task_id>', methods=['POST'])
def submit_gmail_task(task_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    supabase.table("gmail_tasks").update({"status": "Submitted"}).eq("id", task_id).execute()
    flash("জিমেইল একাউন্টটি রিভিউয়ের জন্য এডমিনের কাছে পাঠানো হয়েছে!", "success")
    return redirect(url_for('gmail_tasks'))

# ==========================================
#         ADMIN GMAIL ROUTES
# ==========================================
@app.route('/admin/gmail')
def admin_gmail():
    if not is_admin(): return redirect(url_for('dashboard'))
    tasks = supabase.table("gmail_tasks").select("*").order("created_at", desc=True).execute().data
    return render_template('admin_gmail.html', tasks=tasks)

@app.route('/admin/add_gmail_task', methods=['POST'])
def admin_add_gmail_task():
    if not is_admin(): return redirect(url_for('dashboard'))
    data = {
        "first_name": request.form.get("first_name"),
        "email_prefix": request.form.get("email_prefix"),
        "password_string": request.form.get("password_string"),
        "rate": float(request.form.get("rate")),
        "status": "Available"
    }
    supabase.table("gmail_tasks").insert(data).execute()
    flash("নতুন জিমেইল টাস্ক সফলভাবে অ্যাড করা হয়েছে!", "success")
    return redirect(url_for('admin_gmail'))

@app.route('/admin/gmail_action/<int:task_id>/<action>')
def admin_gmail_action(task_id, action):
    if not is_admin(): return redirect(url_for('dashboard'))
    task = supabase.table("gmail_tasks").select("*").eq("id", task_id).execute().data[0]
    
    if action == 'approve' and task['status'] == 'Submitted':
        # ইউজারকে টাকা দেওয়া হচ্ছে
        u_data = supabase.table("users").select("balance, total_earned").eq("id", task['assigned_user_id']).execute().data[0]
        supabase.table("users").update({
            "balance": u_data['balance'] + task['rate'],
            "total_earned": u_data.get('total_earned', 0) + task['rate']
        }).eq("id", task['assigned_user_id']).execute()
        
        # টাস্ক ডিলিট করা হচ্ছে (কারণ কাজ শেষ)
        supabase.table("gmail_tasks").delete().eq("id", task_id).execute()
        flash(f"কাজটি এপ্রুভ করা হয়েছে এবং ইউজারকে {task['rate']} টাকা পেমেন্ট করা হয়েছে!", "success")
        
    elif action == 'reject' and task['status'] in ['Submitted', 'In Progress']:
        # কাজ রিজেক্ট করে আবার এভেইলেবল করা হচ্ছে
        supabase.table("gmail_tasks").update({
            "status": "Available",
            "assigned_user_id": None,
            "assigned_at": None
        }).eq("id", task_id).execute()
        flash("কাজটি বাতিল করে আবার নতুনদের জন্য উন্মুক্ত করা হয়েছে!", "warning")
        
    elif action == 'delete':
        supabase.table("gmail_tasks").delete().eq("id", task_id).execute()
        flash("টাস্কটি ডিলিট করা হয়েছে!", "danger")
        
    return redirect(url_for('admin_gmail'))
    
if __name__ == '__main__':
    app.run(debug=True)
