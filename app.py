import streamlit as st
import pandas as pd
import datetime
import altair as alt
import gspread
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
    """
    Deletes old logs for the specific date and rewrite the updated list.
    This allows 'Editing' and 'Deleting' history to sync with cloud.
    """
    if not client: return
    sheet = get_tab(client, "Sheet1")
    if not sheet: return
    
    try:
        # 1. Get all data
        all_vals = sheet.get_all_values()
        if not all_vals: return
        
        # 2. Filter out rows that MATCH today's date (we will replace them)
        # Assuming Date is Column 1 (index 0)
        # Keep header (row 0) and rows that are NOT today
        new_rows = [row for row in all_vals if row[0] != date_str]
        
        # 3. Append the NEW updated logs for today
        for entry in log_data:
            # Only save if it matches today (safety check)
            if str(entry['date']) == date_str:
                new_rows.append([
                    str(entry['date']), 
                    entry['name'], 
                    str(entry['cal']), 
                    entry['type'],
                    str(entry.get('amount', 1)), # Save amount if exists
                    str(entry.get('unit', ''))   # Save unit if exists
                ])
        
        # 4. Clear and Update Sheet
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

# --- 5. LOGIC & DATA ---

# Added 'cal_per_unit' for auto-calc
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal_per_unit': 350, 'unit': 'Bowl'},
    {'name': 'Egg White Omelet', 'cal_per_unit': 250, 'unit': 'Serving'},
    {'name': 'Avocado Toast', 'cal_per_unit': 400, 'unit': 'Slice'},
    {'name': 'Grilled Chicken Salad', 'cal_per_unit': 450, 'unit': 'Bowl'},
    {'name': 'Quinoa Power Bowl', 'cal_per_unit': 500, 'unit': 'Bowl'},
    {'name': 'Grilled Salmon', 'cal_per_unit': 600, 'unit': 'Fillet'},
    {'name': 'Lean Steak & Veg', 'cal_per_unit': 700, 'unit': 'Plate'},
    {'name': 'Protein Shake', 'cal_per_unit': 180, 'unit': 'Bottle'},
    {'name': 'Almonds', 'cal_per_unit': 170, 'unit': '30g'},
    {'name': 'Apple', 'cal_per_unit': 80, 'unit': 'Piece'}
])

# Added burn rate (cal per minute)
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
    # fuzzy match activity
    act_key = next((k for k in multi if k in activity), "Sedentary")
    return bmr * multi[act_key]

# --- 6. AUTO-CALCULATION CALLBACKS ---
def update_food_cal():
    """Auto-updates calorie input when food is selected"""
    item = st.session_state.get('food_select')
    qty = st.session_state.get('food_qty', 1.0)
    
    if item and item != "Custom..." and item in FOOD_DB['name'].values:
        base = FOOD_DB.loc[FOOD_DB['name'] == item, 'cal_per_unit'].values[0]
        total = base * qty
        st.session_state['food_cal_input'] = float(total)

def update_ex_cal():
    """Auto-updates burn input when exercise is selected"""
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
                            if isinstance(gs, str): gs = [x.strip() for x in gs.split(',')]
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

# --- 8. MAIN APP & SIDEBAR ---
st.sidebar.markdown(f"### 👤 {st.session_state.real_name}")
# KJ SWITCH
use_kj = st.sidebar.toggle("Use Kilojoules (kJ)", value=False)
unit_label = "kJ" if use_kj else "kcal"
conv = 4.184 if use_kj else 1.0

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()
nav = st.sidebar
