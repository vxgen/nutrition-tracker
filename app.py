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
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    div[data-testid="stExpander"] details summary p { font-size: 1.1rem; font-weight: 600; }
    .block-container { padding-top: 1rem; }
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
            
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
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
    """Verifies user credentials AND approval status."""
    users_sheet = get_tab(client, "users")
    if not users_sheet: return "ERROR"
    
    records = users_sheet.get_all_records()
    for user in records:
        if str(user.get('username')) == username and str(user.get('password')) == password:
            # CHECK APPROVAL STATUS
            status = str(user.get('status', '')).lower().strip()
            if status == 'approved':
                return user.get('name')
            else:
                return "PENDING"
    return None

def register_user(username, password, name, client):
    """Adds a new user with 'pending' status."""
    users_sheet = get_tab(client, "users")
    if not users_sheet: return False, "System Error"
    
    records = users_sheet.get_all_records()
    for user in records:
        if str(user.get('username')) == username:
            return False, "Username already exists."
    
    # Save with status 'pending'
    users_sheet.append_row([username, password, name, str(datetime.date.today()), 'pending'])
    return True, "Account created! Please wait for admin approval."

def load_latest_profile(username, client):
    p_sheet = get_tab(client, "profiles")
    if not p_sheet: return None
    all_data = p_sheet.get_all_records()
    user_history = [row for row in all_data if str(row.get('username')) == username]
    return user_history[-1] if user_history else None

def save_profile_update(username, data, client):
    p_sheet = get_tab(client, "profiles")
    if p_sheet:
        row = [
            username, str(datetime.date.today()),
            data['weight'], data['height'], data['age'], 
            data['gender'], data['activity'], data['goal']
        ]
        p_sheet.append_row(row)

# --- 4. SESSION STATE ---
if 'client' not in st.session_state:
    st.session_state.client = connect_to_google()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.real_name = None

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'target': 2000, 'goals': ['Maintain']}

if 'food_log' not in st.session_state:
    st.session_state.food_log = []

# --- 5. LOGIC & DATA ---
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast'},
    {'name': 'Egg White Omelet', 'cal': 250, 'type': 'Breakfast'},
    {'name': 'Avocado Toast', 'cal': 400, 'type': 'Breakfast'},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch'},
    {'name': 'Grilled Salmon', 'cal': 600, 'type': 'Dinner'},
    {'name': 'Lean Steak', 'cal': 700, 'type': 'Dinner'},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack'},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack'}
])

GOAL_DB = {
    "Maintain Weight": 0, "Lose Weight (Slow)": -250, 
    "Lose Weight (Fast)": -500, "Build Muscle": 300
}

def calculate_target(weight, height, age, gender, activity, goal):
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161
    multipliers = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    tdee = bmr * multipliers.get(activity, 1.2)
    return int(tdee + GOAL_DB.get(goal, 0))

# --- 6. AUTHENTICATION ---
if not st.session_state.logged_in:
    st.title("🔒 NutriTrack Login")
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Login", use_container_width=True):
                if st.session_state.client:
                    result = check_login(user, pw, st.session_state.client)
                    if result == "PENDING":
                        st.warning("⏳ Account pending approval. Please contact admin.")
                    elif result == "ERROR":
                         st.error("System Error: 'users' tab missing.")
                    elif result:
                        st.session_state.logged_in = True
                        st.session_state.username = user
                        st.session_state.real_name = result
                        
                        # Load Profile
                        profile = load_latest_profile(user, st.session_state.client)
                        if profile:
                            st.session_state.user_profile = profile
                            tgt = calculate_target(profile['weight'], profile['height'], profile['age'], profile['gender'], profile['activity'], profile['goal'])
                            st.session_state.user_profile['target'] = tgt
                        
                        # Load Logs
                        log_sheet = get_tab(st.session_state.client, "Sheet1")
                        if log_sheet: st.session_state.food_log = log_sheet.get_all_records()
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")

    with tab2:
        with st.form("signup"):
            nu, np = st.text_input("New User"), st.text_input("New Password", type="password")
            nn = st.text_input("Display Name")
            if st.form_submit_button("Register"):
                if st.session_state.client:
                    ok, msg = register_user(nu, np, nn, st.session_state.client)
                    if ok: st.success(msg)
                    else: st.error(msg)
    st.stop()

# --- 7. MAIN APP ---
st.sidebar.markdown(f"### 👤 {st.session_state.real_name}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()
nav = st.sidebar.radio("Navigation", ["📝 Daily Tracker", "📊 Analytics", "📅 Planner", "👤 Profile"])

if nav == "📝 Daily Tracker":
    st.header("📝 Daily Tracker")
    today_str = str(datetime.date.today())
    today_logs = [x for x in st.session_state.food_log if str(x.get('date')) == today_str]
    
    # --- CALCULATION FIX ---
    # 1. Filter out 'Profile_Settings' to fix the 2200 ghost calories
    # 2. Separate Food vs Exercise
    food_logs = [x for x in today_logs if x['type'] not in ['Exercise', 'Profile_Settings']]
    exercise_logs = [x for x in today_logs if x['type'] == 'Exercise']
    
    consumed = sum(entry['cal'] for entry in food_logs)
    burned = sum(entry['cal'] for entry in exercise_logs)
    
    base_target = st.session_state.user_profile.get('target', 2000)
    # Logic: Target increases if you burn calories
    adjusted_target = base_target + burned
    remaining = adjusted_target - consumed
    
    # METRICS
    c1, c2, c3 = st.columns(3)
    c1.metric("Food Intake", f"{consumed} kcal")
    c2.metric("Exercise Burned", f"{burned} kcal")
    c3.metric("Remaining", f"{remaining} kcal", 
              delta=f"{burned} earned" if burned > 0 else None)
    
    st.progress(min(consumed/adjusted_target if adjusted_target > 0 else 1.0, 1.0))
    st.divider()
    
    # INPUT TABS
    tab_food, tab_ex = st.tabs(["🍽️ Add Meal", "🏃 Add Exercise"])
    
    with tab_food:
        with st.form("add_meal"):
            c_name, c_cal = st.columns([2, 1])
            name = c_name.text_input("Food Name")
            cal = c_cal.number_input("Calories", min_value=0, step=10)
            if st.form_submit_button("Add Food"):
                new_entry = {'date': today_str, 'name': name, 'cal': cal, 'type': 'Manual'}
                sheet1 = get_tab(st.session_state.client, "Sheet1")
                if sheet1:
                    sheet1.append_row([today_str, name, cal, 'Manual'])
                    st.session_state.food_log.append(new_entry)
                    st.rerun()

    with tab_ex:
        with st.form("add_exercise"):
            c_ex, c_burn = st.columns([2, 1])
            ex_name = c_ex.text_input("Exercise (e.g., Running 5k)")
            ex_cal = c_burn.number_input("Calories Burned", min_value=0, step=10)
            if st.form_submit_button("Add Exercise"):
                # Save exercise with type 'Exercise'
                new_entry = {'date': today_str, 'name': ex_name, 'cal': ex_cal, 'type': 'Exercise'}
                sheet1 = get_tab(st.session_state.client, "Sheet1")
                if sheet1:
                    sheet1.append_row([today_str, ex_name, ex_cal, 'Exercise'])
                    st.session_state.food_log.append(new_entry)
                    st.success(f"Added {ex_name} (-{ex_cal} kcal)")
                    st.rerun()

    # LOG DISPLAY (Hide Profile Updates from view)
    if today_logs:
        st.subheader("Today's Log")
        display_logs = [x for x in today_logs if x['type'] != 'Profile_Settings']
        st.dataframe(pd.DataFrame(display_logs)[['name', 'cal', 'type']], use_container_width=True)

# ... (Rest of pages: Analytics, Planner, Profile remain the same as previous) ...
elif nav == "📊 Analytics":
    st.header("📊 Progress & Trends")
    p_sheet = get_tab(st.session_state.client, "profiles")
    if p_sheet:
        all_records = p_sheet.get_all_records()
        user_records = [r for r in all_records if str(r.get('username')) == st.session_state.username]
        if user_records:
            df = pd.DataFrame(user_records)
            df['date'] = pd.to_datetime(df['date'])
            df['weight'] = pd.to_numeric(df['weight'])
            
            st.subheader("Weight Tracking")
            filter_option = st.selectbox("Time Range", ["Last 7 Days", "Last 30 Days", "Last 3 Months", "All Time"])
            end_date = datetime.datetime.now()
            if filter_option == "Last 7 Days": start = end_date - datetime.timedelta(days=7)
            elif filter_option == "Last 30 Days": start = end_date - datetime.timedelta(days=30)
            elif filter_option == "Last 3 Months": start = end_date - datetime.timedelta(days=90)
            else: start = end_date - datetime.timedelta(days=3650)
            
            mask = (df['date'] >= start) & (df['date'] <= end_date)
            filtered_df = df.loc[mask]
            
            if not filtered_df.empty:
                chart = alt.Chart(filtered_df).mark_line(point=True, color='teal').encode(
                    x=alt.X('date:T', title='Date'),
                    y=alt.Y('weight:Q', scale=alt.Scale(zero=False), title='Weight (kg)'),
                    tooltip=['date', 'weight']
                ).properties(height=350)
                st.altair_chart(chart, use_container_width=True)
            else: st.info("No data for this time range.")
        else: st.info("No profile history found.")

elif nav == "📅 Planner":
    st.header("📅 Smart Meal Planner")
    current_target = st.session_state.user_profile.get('target', 2000)
    st.write(f"Generating plan for target: **{current_target} kcal**")
    if st.button("Generate New Plan"):
        plan = []
        total_cal = 0
        attempts = 0
        while total_cal < (current_target - 200) and attempts < 10:
            item = FOOD_DB.sample(1).iloc[0]
            plan.append(item.to_dict())
            total_cal += item['cal']
            attempts += 1
        st.session_state.generated_plan = plan
    if 'generated_plan' in st.session_state:
        for item in st.session_state.generated_plan:
            st.write(f"**{item['type']}**: {item['name']} - {item['cal']} kcal")

elif nav == "👤 Profile":
    st.header("👤 Update Profile")
    curr = st.session_state.user_profile
    with st.form("profile_update"):
        c1, c2 = st.columns(2)
        w = c1.number_input("Weight (kg)", value=float(curr.get('weight', 70)))
        h = c2.number_input("Height (cm)", value=int(curr.get('height', 170)))
        a = c1.number_input("Age", value=int(curr.get('age', 30)))
        g = c2.selectbox("Gender", ["Male", "Female"], index=0 if curr.get('gender') == 'Male' else 1)
        act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"], index=0)
        goal = st.selectbox("Goal", list(GOAL_DB.keys()), index=0)
        
        if st.form_submit_button("💾 Save & Update"):
            new_target = calculate_target(w, h, a, g, act, goal)
            updated_data = {'weight': w, 'height': h, 'age': a, 'gender': g, 'activity': act, 'goal': goal, 'target': new_target}
            st.session_state.user_profile = updated_data
            if st.session_state.client:
                save_profile_update(st.session_state.username, updated_data, st.session_state.client)
                st.success(f"Updated! New Target: {new_target} kcal")
                st.rerun()
