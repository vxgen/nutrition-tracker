import streamlit as st
import pandas as pd
import datetime
import altair as alt
import gspread
import random
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION ---
st.set_page_config(
    page_title="NutriTrack Pro", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .block-container { padding-top: 1rem; }
    div.stButton > button:first-child { font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- 2. GOOGLE SHEETS CONNECTION ---
@st.cache_resource
def connect_to_google():
    try:
        if "service_account" in st.secrets:
            key_dict = dict(st.secrets["service_account"])
            if "\\n" in key_dict["private_key"]:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
            client = gspread.authorize(creds)
            return client
        return None
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

# --- 3. DATABASE HELPERS ---
def get_tab(client, tab_name):
    try:
        sheet = client.open("NutriTrack_Data")
        return sheet.worksheet(tab_name)
    except Exception:
        return None

def check_login(username, password, client):
    users_sheet = get_tab(client, "users")
    if not users_sheet: return "ERROR"
    records = users_sheet.get_all_records()
    for user in records:
        if str(user.get('username')) == username and str(user.get('password')) == password:
            status = str(user.get('status', '')).lower().strip()
            if status == 'approved':
                return user.get('name')
            else:
                return "PENDING"
    return None

def register_user(username, password, name, client):
    users_sheet = get_tab(client, "users")
    if not users_sheet: return False, "System Error"
    records = users_sheet.get_all_records()
    for user in records:
        if str(user.get('username')) == username:
            return False, "Username already exists."
    users_sheet.append_row([username, password, name, str(datetime.date.today()), 'pending'])
    return True, "Account created! Wait for admin approval."

def load_latest_profile(username, client):
    p_sheet = get_tab(client, "profiles")
    if not p_sheet: return None
    all_data = p_sheet.get_all_records()
    user_history = [row for row in all_data if str(row.get('username')) == username]
    return user_history[-1] if user_history else None

def save_profile_update(username, data, client):
    p_sheet = get_tab(client, "profiles")
    if p_sheet:
        goals_str = ", ".join(data['goals'])
        row = [
            username, str(datetime.date.today()),
            data['weight'], data['height'], data['age'], 
            data['gender'], data['activity'], goals_str
        ]
        p_sheet.append_row(row)

def sync_log_to_sheet(client, log_data, date_str):
    if not client: return
    sheet = get_tab(client, "Sheet1")
    if not sheet: return
    
    try:
        all_vals = sheet.get_all_values()
        if not all_vals: return
        
        # Filter keep old rows
        new_rows = [row for row in all_vals if row[0] != date_str]
        
        # Append new logs
        for entry in log_data:
            if str(entry['date']) == date_str:
                new_rows.append([
                    str(entry['date']), 
                    entry['name'], 
                    str(entry['cal']), 
                    entry['type'],
                    str(entry.get('amount', 1)),
                    str(entry.get('unit', ''))
                ])
        
        sheet.clear()
        sheet.update(new_rows)
        
    except Exception as e:
        print(f"Sync Error: {e}")

# --- 4. SESSION STATE & CALLBACKS ---
if 'client' not in st.session_state:
    st.session_state.client = connect_to_google()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.real_name = None
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'target': 2000, 'goals': ['Maintain Current Weight']}
if 'food_log' not in st.session_state:
    st.session_state.food_log = []
if 'generated_plan' not in st.session_state:
    st.session_state.generated_plan = {} # Changed to Dict for multiple days

# --- 5. DATA ---

FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal_per_unit': 350, 'unit': 'Bowl', 'type': 'Breakfast'},
    {'name': 'Egg White Omelet', 'cal_per_unit': 250, 'unit': 'Serving', 'type': 'Breakfast'},
    {'name': 'Avocado Toast', 'cal_per_unit': 400, 'unit': 'Slice', 'type': 'Breakfast'},
    {'name': 'Greek Yogurt Parfait', 'cal_per_unit': 300, 'unit': 'Bowl', 'type': 'Breakfast'},
    
    {'name': 'Grilled Chicken Salad', 'cal_per_unit': 450, 'unit': 'Bowl', 'type': 'Lunch'},
    {'name': 'Quinoa Power Bowl', 'cal_per_unit': 500, 'unit': 'Bowl', 'type': 'Lunch'},
    {'name': 'Turkey Wrap', 'cal_per_unit': 400, 'unit': 'Wrap', 'type': 'Lunch'},
    {'name': 'Tuna Salad', 'cal_per_unit': 350, 'unit': 'Serving', 'type': 'Lunch'},

    {'name': 'Grilled Salmon', 'cal_per_unit': 600, 'unit': 'Fillet', 'type': 'Dinner'},
    {'name': 'Lean Steak & Veg', 'cal_per_unit': 700, 'unit': 'Plate', 'type': 'Dinner'},
    {'name': 'Veggie Stir Fry', 'cal_per_unit': 550, 'unit': 'Bowl', 'type': 'Dinner'},
    {'name': 'Baked Cod', 'cal_per_unit': 500, 'unit': 'Fillet', 'type': 'Dinner'},

    {'name': 'Protein Shake', 'cal_per_unit': 180, 'unit': 'Bottle', 'type': 'Snack'},
    {'name': 'Almonds', 'cal_per_unit': 170, 'unit': '30g', 'type': 'Snack'},
    {'name': 'Apple', 'cal_per_unit': 80, 'unit': 'Piece', 'type': 'Snack'},
    {'name': 'Hummus & Carrots', 'cal_per_unit': 200, 'unit': 'Serving', 'type': 'Snack'}
])

EXERCISE_DB = pd.DataFrame([
    {'name': 'Running (Moderate)', 'cal_per_min': 10},
    {'name': 'Running (Fast)', 'cal_per_min': 14},
    {'name': 'Cycling', 'cal_per_min': 8},
    {'name': 'Swimming', 'cal_per_min': 9},
    {'name': 'Weight Lifting', 'cal_per_min': 4},
    {'name': 'Yoga', 'cal_per_min': 3},
    {'name': 'HIIT', 'cal_per_min': 12},
    {'name': 'Walking (Brisk)', 'cal_per_min': 5},
    {'name': 'Hiking', 'cal_per_min': 6}
])

GOAL_DB = {
    "Maintain Current Weight": 0,
    "Lose Weight (Slow)": -250, "Lose Weight (Standard)": -500, "Lose Weight (Aggressive)": -750,
    "Build Muscle (Lean)": 300, "Build Muscle (Bulk)": 600,
    "Marathon Training": 800, "Triathlon Training": 700, "HIIT Performance": 450,
    "Diabetes (Low Sugar)": -200, "Heart Health": -100, "PCOS": -250, "Pregnancy": 350
}

ACTIVITY_LEVELS = ["Sedentary (Office Job)", "Lightly Active (1-3 days)", "Moderately Active (3-5 days)", "Very Active (6-7 days)", "Athlete (2x per day)"]

def calculate_target(tdee, goals):
    if isinstance(goals, str): goals = [goals]
    adj = sum([GOAL_DB.get(g, 0) for g in goals])
    return max(int(tdee + adj), 1200)

def calculate_bmr_tdee(weight, height, age, gender, activity):
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161
    multi = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725, "Athlete": 1.9}
    act_key = next((k for k in multi if k in activity), "Sedentary")
    return bmr * multi[act_key]

# --- 6. CALLBACKS ---
def update_food_cal():
    item = st.session_state.get('food_select')
    qty = st.session_state.get('food_qty', 1.0)
    if item and item != "Custom..." and item in FOOD_DB['name'].values:
        base = FOOD_DB.loc[FOOD_DB['name'] == item, 'cal_per_unit'].values[0]
        total = base * qty
        st.session_state['food_cal_input'] = float(total)

def update_ex_cal():
    item = st.session_state.get('ex_select')
    mins = st.session_state.get('ex_mins', 30)
    if item and item != "Custom..." and item in EXERCISE_DB['name'].values:
        rate = EXERCISE_DB.loc[EXERCISE_DB['name'] == item, 'cal_per_min'].values[0]
        total = rate * mins
        st.session_state['ex_cal_input'] = float(total)

# --- 7. AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("🔒 NutriTrack Login")
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    with tab1:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                if st.session_state.client:
                    res = check_login(u, p, st.session_state.client)
                    if res == "PENDING": st.warning("⏳ Account pending approval.")
                    elif res == "ERROR": st.error("System Error.")
                    elif res:
                        st.session_state.logged_in = True
                        st.session_state.username = u
                        st.session_state.real_name = res
                        prof = load_latest_profile(u, st.session_state.client)
                        if prof:
                            gs = prof.get('goal', 'Maintain')
                            if isinstance(gs, str): gs = [x.strip() for x in gs.split(',') if x.strip()]
                            gs = [g for g in gs if g in GOAL_DB]
                            if not gs: gs = ['Maintain Current Weight']
                            st.session_state.user_profile = prof
                            st.session_state.user_profile['goals'] = gs
                            t = calculate_bmr_tdee(prof['weight'], prof['height'], prof['age'], prof['gender'], prof['activity'])
                            st.session_state.user_profile['target'] = calculate_target(t, gs)
                        ls = get_tab(st.session_state.client, "Sheet1")
                        if ls: st.session_state.food_log = ls.get_all_records()
                        st.rerun()
                    else: st.error("Invalid credentials.")
    with tab2:
        with st.form("signup"):
            nu, np = st.text_input("User"), st.text_input("Pass", type="password")
            nn = st.text_input("Name")
            if st.form_submit_button("Register"):
                if st.session_state.client:
                    ok, msg = register_user(nu, np, nn, st.session_state.client)
                    if ok: st.success(msg)
                    else: st.error(msg)
    st.stop()

# --- 8. MAIN APP ---
st.sidebar.markdown(f"### 👤 {st.session_state.real_name}")
use_kj = st.sidebar.toggle("Use Kilojoules (kJ)", value=False)
unit_label = "kJ" if use_kj else "kcal"
conv = 4.184 if use_kj else 1.0

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()
nav = st.sidebar.radio("Navigation", ["📝 Daily Tracker", "📊 Analytics", "📅 Planner", "👤 Profile"])

# --- PAGE: TRACKER ---
if nav == "📝 Daily Tracker":
    st.header(f"📝 Daily Tracker ({unit_label})")
    today_str = str(datetime.date.today())
    
    # FILTER LOGS
    all_logs = st.session_state.food_log
    today_logs = [x for x in all_logs if str(x.get('date')) == today_str and x.get('type') in ['Manual', 'Exercise']]
    
    food_sum = sum([float(x['cal']) for x in today_logs if x['type'] == 'Manual'])
    burn_sum = sum([float(x['cal']) for x in today_logs if x['type'] == 'Exercise'])
    
    base_target = st.session_state.user_profile.get('target', 2000)
    final_target = base_target + burn_sum
    remaining = final_target - food_sum
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Food", f"{int(food_sum * conv)} {unit_label}")
    c2.metric("Exercise", f"{int(burn_sum * conv)} {unit_label}")
    c3.metric("Remaining", f"{int(remaining * conv)} {unit_label}", delta="Earned" if burn_sum > 0 else None)
    
    tab_food, tab_ex = st.tabs(["🍽️ Add Meal", "🏃 Add Exercise"])
    
    with tab_food:
        c1, c2, c3 = st.columns([2, 1, 1])
        f_opts = ["Custom..."] + list(FOOD_DB['name'].unique())
        sel_food = c1.selectbox("Food", f_opts, key='food_select', on_change=update_food_cal)
        qty = c2.number_input("Amount (Serving)", 0.5, 10.0, 1.0, step=0.5, key='food_qty', on_change=update_food_cal)
        cal = c3.number_input(f"Calories (kcal)", 0.0, 5000.0, step=10.0, key='food_cal_input')
        
        if st.button("➕ Add Food"):
            name = st.session_state.get('custom_food_name') if sel_food == "Custom..." else sel_food
            if sel_food == "Custom..." and not name: name = st.text_input("Enter Food Name", key="custom_food_name")
            if name and cal > 0:
                new_entry = {'date': today_str, 'name': name, 'cal': cal, 'type': 'Manual', 'amount': qty, 'unit': 'Serving'}
                st.session_state.food_log.append(new_entry)
                sync_log_to_sheet(st.session_state.client, st.session_state.food_log, today_str)
                st.toast(f"Added {name}")
                st.rerun()
                
    with tab_ex:
        c1, c2, c3 = st.columns([2, 1, 1])
        e_opts = ["Custom..."] + list(EXERCISE_DB['name'].unique())
        sel_ex = c1.selectbox("Exercise", e_opts, key='ex_select', on_change=update_ex_cal)
        mins = c2.number_input("Duration (mins)", 5, 180, 30, step=5, key='ex_mins', on_change=update_ex_cal)
        ex_cal = c3.number_input(f"Burned (kcal)", 0.0, 5000.0, step=10.0, key='ex_cal_input')
        
        if st.button("🏃 Add Exercise"):
            name = st.session_state.get('custom_ex_name') if sel_ex == "Custom..." else sel_ex
            if sel_ex == "Custom..." and not name: name = st.text_input("Enter Exercise Name", key="custom_ex_name")
            if name and ex_cal > 0:
                new_entry = {'date': today_str, 'name': name, 'cal': ex_cal, 'type': 'Exercise', 'amount': mins, 'unit': 'mins'}
                st.session_state.food_log.append(new_entry)
                sync_log_to_sheet(st.session_state.client, st.session_state.food_log, today_str)
                st.toast(f"Added {name}")
                st.rerun()

    # 4. HISTORY (FIXED MISSING COLS)
    st.subheader("Today's History (Edit/Delete)")
    if today_logs:
        df = pd.DataFrame(today_logs)
        for col in ['amount', 'unit']:
            if col not in df.columns: df[col] = 1.0 if col == 'amount' else ''
        
        edited_df = st.data_editor(
            df[['name', 'cal', 'type', 'amount', 'unit']],
            column_config={
                "cal": st.column_config.NumberColumn("Calories (kcal)"),
                "amount": st.column_config.NumberColumn("Qty/Mins"),
            },
            num_rows="dynamic",
            use_container_width=True,
            key="history_editor"
        )
        
        if not df[['name', 'cal', 'type', 'amount', 'unit']].equals(edited_df):
            if st.button("💾 Save Changes to Cloud"):
                kept_logs = [x for x in st.session_state.food_log if str(x.get('date')) != today_str]
                new_logs = edited_df.to_dict('records')
                for n in new_logs: n['date'] = today_str
                final_log = kept_logs + new_logs
                st.session_state.food_log = final_log
                sync_log_to_sheet(st.session_state.client, final_log, today_str)
                st.success("History updated!")
                st.rerun()
    else:
        st.info("No logs for today.")

# --- PAGE: ANALYTICS (FIXED TYPO) ---
elif nav == "📊 Analytics":
    st.header("📊 Analytics")
    p_sheet = get_tab(st.session_state.client, "profiles")
    if p_sheet:
        all_records = p_sheet.get_all_records()
        user_records = [r for r in all_records if str(r.get('username')) == st.session_state.username]
        if user_records:
            df = pd.DataFrame(user_records)
            df.columns = [c.lower() for c in df.columns]
            df = df.rename(columns={'data': 'date'}) # <--- TYPO FIX
            
            if 'date' in df.columns and 'weight' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['weight'] = pd.to_numeric(df['weight'])
                chart = alt.Chart(df).mark_line(point=True).encode(x='date:T', y=alt.Y('weight', scale=alt.Scale(zero=False))).properties(title="Weight Trend")
                st.altair_chart(chart, use_container_width=True)
            else:
                st.error(f"❌ Data Error: Columns found: {list(df.columns)}. Expected 'date' and 'weight'.")
        else:
            st.info("No profile history found.")

# --- PAGE: PLANNER (RESTORED & EXPANDED) ---
elif nav == "📅 Planner":
    st.header("📅 Smart Meal Planner")
    current_target = st.session_state.user_profile.get('target', 2000)
    
    col_p1, col_p2 = st.columns([3, 1])
    col_p1.write(f"Generating plan for target: **{current_target} kcal/day**")
    
    # 1. Select Duration
    duration = col_p2.selectbox("Plan Duration", ["Today's Plan", "Weekly (7 Days)", "Monthly (30 Days)"])
    
    if st.button("🎲 Generate Meal Plan"):
        days = 1
        if "Weekly" in duration: days = 7
        if "Monthly" in duration: days = 30
        
        full_plan = {} # Dictionary to store days
        
        for d in range(1, days + 1):
            day_plan = []
            current_cal = 0
            attempts = 0
            
            # Logic: Ensure 1 Breakfast, 1 Lunch, 1 Dinner first
            for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
                # Filter DB for specific meal type
                options = FOOD_DB[FOOD_DB['type'] == meal_type]
                if not options.empty:
                    item = options.sample(1).iloc[0].to_dict()
                    day_plan.append(item)
                    current_cal += item['cal_per_unit']
            
            # Fill remaining calories with Snacks
            while current_cal < (current_target - 150) and attempts < 20:
                options = FOOD_DB[FOOD_DB['type'] == 'Snack']
                if not options.empty:
                    item = options.sample(1).iloc[0].to_dict()
                    day_plan.append(item)
                    current_cal += item['cal_per_unit']
                attempts += 1
                
            full_plan[f"Day {d}"] = day_plan
            
        st.session_state.generated_plan = full_plan

    # 2. Display Plan
    if st.session_state.generated_plan:
        st.divider()
        st.subheader(f"🥗 Your {duration}")
        
        # Iterate through days
        for day_label, meals in st.session_state.generated_plan.items():
            # Calculate total cals for the day
            day_total = sum(m['cal_per_unit'] for m in meals)
            
            with st.expander(f"**{day_label}** - {day_total} kcal"):
                for item in meals:
                    c1, c2, c3 = st.columns([2, 1, 1])
                    c1.write(f"**{item['type']}**: {item['name']}")
                    c2.write(f"{item['cal_per_unit']} kcal")
                    c3.write(f"_{item['unit']}_")

# --- PAGE: PROFILE ---
elif nav == "👤 Profile":
    st.header("👤 Profile Settings")
    curr = st.session_state.user_profile
    with st.form("prof"):
        w = st.number_input("Weight (kg)", value=float(curr.get('weight', 70)))
        h = st.number_input("Height (cm)", value=int(curr.get('height', 170)))
        a = st.number_input("Age", value=int(curr.get('age', 30)))
        g = st.selectbox("Gender", ["Male", "Female"], index=0 if curr.get('gender')=='Male' else 1)
        
        act_idx = 0
        if curr.get('activity') in ACTIVITY_LEVELS:
            act_idx = ACTIVITY_LEVELS.index(curr.get('activity'))
        act = st.selectbox("Activity", ACTIVITY_LEVELS, index=act_idx)
        
        goals = st.multiselect("Goals", list(GOAL_DB.keys()), default=curr.get('goals', ['Maintain Current Weight']))
        
        if st.form_submit_button("Update"):
            t = calculate_bmr_tdee(w, h, a, g, act)
            tgt = calculate_target(t, goals)
            upd = {'weight': w, 'height': h, 'age': a, 'gender': g, 'activity': act, 'goals': goals, 'target': tgt}
            st.session_state.user_profile = upd
            save_profile_update(st.session_state.username, upd, st.session_state.client)
            st.success(f"Saved! New Target: {tgt} kcal")
            st.rerun()
