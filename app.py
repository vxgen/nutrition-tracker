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

# Custom CSS for UI polish
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 1.8rem; }
    .block-container { padding-top: 1rem; }
    /* Highlight the add button */
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
        # Save goals as a comma-separated string
        goals_str = ", ".join(data['goals'])
        row = [
            username, str(datetime.date.today()),
            data['weight'], data['height'], data['age'], 
            data['gender'], data['activity'], goals_str
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
    st.session_state.user_profile = {'target': 2000, 'goals': ['Maintain Current Weight']}
if 'food_log' not in st.session_state:
    st.session_state.food_log = []

# --- 5. LOGIC & DATA ---
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast'},
    {'name': 'Egg White Omelet', 'cal': 250, 'type': 'Breakfast'},
    {'name': 'Avocado Toast', 'cal': 400, 'type': 'Breakfast'},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch'},
    {'name': 'Quinoa Power Bowl', 'cal': 500, 'type': 'Lunch'},
    {'name': 'Grilled Salmon', 'cal': 600, 'type': 'Dinner'},
    {'name': 'Lean Steak & Veg', 'cal': 700, 'type': 'Dinner'},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack'},
    {'name': 'Almonds (30g)', 'cal': 170, 'type': 'Snack'},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack'}
])

EXERCISE_DB = [
    "Running (Moderate)", "Running (Fast)", "Cycling", "Swimming", 
    "Weight Lifting", "Yoga", "HIIT", "Walking (Brisk)", "Hiking"
]

GOAL_DB = {
    # Weight
    "Maintain Current Weight": 0,
    "Lose Weight (Slow & Steady)": -250,
    "Lose Weight (Standard)": -500,
    "Lose Weight (Aggressive)": -750,
    "Weight Gain (Muscle)": 300,
    # Fitness
    "Build Muscle (Lean Bulk)": 300,
    "Build Muscle (Dirty Bulk)": 600,
    "Marathon / Ultra Training": 800,
    "Triathlon Training": 700,
    "Cycling (Endurance)": 600,
    "Swimming (Competitive)": 500,
    "Strength Training / Powerlifting": 400,
    "CrossFit / HIIT Performance": 450,
    # Health
    "Manage Type 2 Diabetes (Low Sugar)": -200,
    "Heart Health (Low Sodium)": -100,
    "PCOS Management": -250,
    "IBS / Low FODMAP": 0,
    "Celiac / Gluten Free": 0,
    # Life Stages
    "Pregnancy (2nd/3rd Trimester)": 350,
    "Breastfeeding": 500,
    "Improve Energy / Fatigue": 0
}

ACTIVITY_LEVELS = [
    "Sedentary (Office Job)",
    "Lightly Active (1-3 days)",
    "Moderately Active (3-5 days)",
    "Very Active (6-7 days)",
    "Athlete (2x per day)"
]

def calculate_target_from_goals(tdee, selected_goals):
    adjustment = 0
    # Robustly handle list vs string inputs
    if isinstance(selected_goals, str):
        selected_goals = [selected_goals]
    
    for goal in selected_goals:
        adjustment += GOAL_DB.get(goal, 0)
    return max(int(tdee + adjustment), 1200)

def calculate_bmr_tdee(weight, height, age, gender, activity):
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161
    multipliers = {
        "Sedentary (Office Job)": 1.2,
        "Lightly Active (1-3 days)": 1.375,
        "Moderately Active (3-5 days)": 1.55,
        "Very Active (6-7 days)": 1.725,
        "Athlete (2x per day)": 1.9
    }
    return bmr * multipliers.get(activity, 1.2)

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
                        st.warning("⏳ Account pending approval. Contact admin.")
                    elif result == "ERROR":
                         st.error("System Error: 'users' tab missing.")
                    elif result:
                        st.session_state.logged_in = True
                        st.session_state.username = user
                        st.session_state.real_name = result
                        
                        # Load Profile
                        profile = load_latest_profile(user, st.session_state.client)
                        if profile:
                            # Robust Goal Loading (String -> List)
                            saved_goals = profile.get('goal', 'Maintain Current Weight')
                            if isinstance(saved_goals, str):
                                if "," in saved_goals:
                                    saved_goals = [g.strip() for g in saved_goals.split(",")]
                                else:
                                    saved_goals = [saved_goals]
                            
                            st.session_state.user_profile = profile
                            st.session_state.user_profile['goals'] = saved_goals
                            
                            tdee = calculate_bmr_tdee(profile['weight'], profile['height'], profile['age'], profile['gender'], profile['activity'])
                            tgt = calculate_target_from_goals(tdee, saved_goals)
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
    
    food_logs = [x for x in today_logs if x['type'] not in ['Exercise', 'Profile_Settings']]
    exercise_logs = [x for x in today_logs if x['type'] == 'Exercise']
    
    consumed = sum(entry['cal'] for entry in food_logs)
    burned = sum(entry['cal'] for entry in exercise_logs)
    base_target = st.session_state.user_profile.get('target', 2000)
    
    adjusted_target = base_target + burned
    remaining = adjusted_target - consumed
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Food Intake", f"{consumed} kcal")
    c2.metric("Exercise Burned", f"{burned} kcal")
    c3.metric("Remaining", f"{remaining} kcal", delta=f"{burned} earned" if burned > 0 else None)
    st.progress(min(consumed/adjusted_target if adjusted_target > 0 else 1.0, 1.0))
    st.divider()
    
    tab_food, tab_ex = st.tabs(["🍽️ Add Meal", "🏃 Add Exercise"])
    
    # --- NO FORMS HERE (Required for auto-update) ---
    with tab_food:
        st.write("### Add Food")
        col_f1, col_f2 = st.columns([2, 1])
        
        # 1. Predictive Dropdown
        food_options = ["Custom..."] + list(FOOD_DB['name'].unique())
        selected_food = col_f1.selectbox("Search Food", food_options, key="food_select")
        
        # 2. Logic to Auto-Fill Calories
        default_cal = 0
        custom_name = ""
        
        if selected_food != "Custom...":
            # Auto-find calories from DB
            match = FOOD_DB[FOOD_DB['name'] == selected_food].iloc[0]
            default_cal = int(match['cal'])
        else:
            custom_name = col_f1.text_input("Enter Custom Food Name")

        # 3. Calorie Input (Pre-filled but editable)
        cal_input = col_f2.number_input("Calories", value=default_cal, min_value=0, step=10, key="food_cal")
        
        if st.button("➕ Add Meal", use_container_width=True):
            final_name = custom_name if selected_food == "Custom..." else selected_food
            if final_name:
                new_entry = {'date': today_str, 'name': final_name, 'cal': cal_input, 'type': 'Manual'}
                sheet1 = get_tab(st.session_state.client, "Sheet1")
                if sheet1:
                    sheet1.append_row([today_str, final_name, cal_input, 'Manual'])
                    st.session_state.food_log.append(new_entry)
                    st.toast(f"Added {final_name}")
                    st.rerun()

    with tab_ex:
        st.write("### Add Exercise")
        col_e1, col_e2 = st.columns([2, 1])
        
        ex_options = ["Custom..."] + EXERCISE_DB
        selected_ex = col_e1.selectbox("Search Exercise", ex_options, key="ex_select")
        
        custom_ex_name = ""
        if selected_ex == "Custom...":
            custom_ex_name = col_e1.text_input("Enter Custom Exercise")
            
        ex_cal_input = col_e2.number_input("Calories Burned", min_value=0, step=10, key="ex_cal")
        
        if st.button("🏃 Add Exercise", use_container_width=True):
            final_ex = custom_ex_name if selected_ex == "Custom..." else selected_ex
            if final_ex:
                new_entry = {'date': today_str, 'name': final_ex, 'cal': ex_cal_input, 'type': 'Exercise'}
                sheet1 = get_tab(st.session_state.client, "Sheet1")
                if sheet1:
                    sheet1.append_row([today_str, final_ex, ex_cal_input, 'Exercise'])
                    st.session_state.food_log.append(new_entry)
                    st.toast(f"Added {final_ex}")
                    st.rerun()

    if today_logs:
        st.subheader("Today's History")
        display_logs = [x for x in today_logs if x['type'] != 'Profile_Settings']
        st.dataframe(pd.DataFrame(display_logs)[['name', 'cal', 'type']], use_container_width=True)

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
            filter_option = st.selectbox("Time Range", ["Last 7 Days", "Last 30 Days", "All Time"])
            end_date = datetime.datetime.now()
            if filter_option == "Last 7 Days": start = end_date - datetime.timedelta(days=7)
            elif filter_option == "Last 30 Days": start = end_date - datetime.timedelta(days=30)
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
    
    # Defaults
    gender_opts = ["Male", "Female"]
    curr_gender = curr.get('gender', 'Male')
    g_idx = gender_opts.index(curr_gender) if curr_gender in gender_opts else 0
    
    curr_act = curr.get('activity', '')
    a_idx = ACTIVITY_LEVELS.index(curr_act) if curr_act in ACTIVITY_LEVELS else 0
    
    # MULTI-GOAL RESTORATION
    curr_goals = curr.get('goals', [])
    if isinstance(curr_goals, str): curr_goals = [curr_goals]
    if not curr_goals: curr_goals = ["Maintain Current Weight"]
    
    # Safety Check: Only keep goals that actually exist in the DB
    valid_goals = [g for g in curr_goals if g in GOAL_DB]
    if not valid_goals: valid_goals = ["Maintain Current Weight"]

    with st.form("profile_update"):
        c1, c2 = st.columns(2)
        w = c1.number_input("Weight (kg)", value=float(curr.get('weight', 70)))
        h = c2.number_input("Height (cm)", value=int(curr.get('height', 170)))
        a = c1.number_input("Age", value=int(curr.get('age', 30)))
        g = c2.selectbox("Gender", gender_opts, index=g_idx)
        act = st.selectbox("Activity Level", ACTIVITY_LEVELS, index=a_idx)
        
        # --- FIXED: MULTISELECT ---
        goals = st.multiselect("Select Goals (Multiple Allowed)", sorted(list(GOAL_DB.keys())), default=valid_goals)
        
        if st.form_submit_button("💾 Save & Update"):
            tdee = calculate_bmr_tdee(w, h, a, g, act)
            new_target = calculate_target_from_goals(tdee, goals)
            
            updated_data = {
                'weight': w, 'height': h, 'age': a, 'gender': g, 
                'activity': act, 'goals': goals, 'target': new_target
            }
            st.session_state.user_profile = updated_data
            if st.session_state.client:
                save_profile_update(st.session_state.username, updated_data, st.session_state.client)
                st.success(f"Updated! New Target: {new_target} kcal")
                st.rerun()
