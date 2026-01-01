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

# Custom CSS for better mobile & desktop UI
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
    """Connects to Google Sheets using existing secrets."""
    try:
        if "service_account" in st.secrets:
            key_dict = dict(st.secrets["service_account"])
            # Fix newlines in private key if needed
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

# --- 3. DATABASE HELPERS (User Management) ---

def get_tab(client, tab_name):
    """Safely gets a specific worksheet tab."""
    try:
        sheet = client.open("NutriTrack_Data")
        return sheet.worksheet(tab_name)
    except Exception:
        st.error(f"Error: Could not find tab '{tab_name}'. Please check your Google Sheet.")
        return None

def check_login(username, password, client):
    """Verifies user credentials against 'users' tab."""
    users_sheet = get_tab(client, "users")
    if not users_sheet: return None
    
    records = users_sheet.get_all_records()
    for user in records:
        # Convert to string to ensure matching works
        if str(user.get('username')) == username and str(user.get('password')) == password:
            return user.get('name') # Return real name on success
    return None

def register_user(username, password, name, client):
    """Adds a new user to 'users' tab."""
    users_sheet = get_tab(client, "users")
    if not users_sheet: return False, "System Error"
    
    records = users_sheet.get_all_records()
    for user in records:
        if str(user.get('username')) == username:
            return False, "Username already exists."
    
    users_sheet.append_row([username, password, name, str(datetime.date.today())])
    return True, "Account created successfully!"

def load_latest_profile(username, client):
    """Fetches the most recent profile data for the user."""
    p_sheet = get_tab(client, "profiles")
    if not p_sheet: return None
    
    all_data = p_sheet.get_all_records()
    # Filter for this username
    user_history = [row for row in all_data if str(row.get('username')) == username]
    
    if user_history:
        # Return the last entry (assumed latest)
        return user_history[-1]
    return None

def save_profile_update(username, data, client):
    """Saves new profile data as a new row (history tracking)."""
    p_sheet = get_tab(client, "profiles")
    if p_sheet:
        row = [
            username,
            str(datetime.date.today()),
            data['weight'],
            data['height'],
            data['age'],
            data['gender'],
            data['activity'],
            data['goal']
        ]
        p_sheet.append_row(row)

# --- 4. SESSION STATE INIT ---
if 'client' not in st.session_state:
    st.session_state.client = connect_to_google()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.real_name = None

if 'user_profile' not in st.session_state:
    # Default placeholder profile
    st.session_state.user_profile = {'target': 2000, 'goals': ['Maintain']}

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

GOAL_DB = {
    "Maintain Weight": 0, 
    "Lose Weight (Slow)": -250, 
    "Lose Weight (Fast)": -500, 
    "Build Muscle": 300,
    "Heart Health": -100
}

def calculate_target(weight, height, age, gender, activity, goal):
    # Mifflin-St Jeor Equation
    bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161
    
    activity_multipliers = {
        "Sedentary": 1.2,
        "Lightly Active": 1.375,
        "Moderately Active": 1.55,
        "Very Active": 1.725
    }
    tdee = bmr * activity_multipliers.get(activity, 1.2)
    target = tdee + GOAL_DB.get(goal, 0)
    return int(target)

# --- 6. AUTHENTICATION FLOW ---
if not st.session_state.logged_in:
    st.title("🔒 NutriTrack Login")
    
    tab1, tab2 = st.tabs(["Login", "Create Account"])
    
    with tab1:
        with st.form("login_form"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
            
            if submitted:
                if st.session_state.client:
                    real_name = check_login(user, pw, st.session_state.client)
                    if real_name:
                        # SUCCESS: Set Session State
                        st.session_state.logged_in = True
                        st.session_state.username = user
                        st.session_state.real_name = real_name
                        
                        # LOAD PROFILE AUTOMATICALLY
                        profile = load_latest_profile(user, st.session_state.client)
                        if profile:
                            st.session_state.user_profile = profile
                            # Recalculate target to ensure it matches current weight
                            tgt = calculate_target(
                                profile['weight'], profile['height'], profile['age'], 
                                profile['gender'], profile['activity'], profile['goal']
                            )
                            st.session_state.user_profile['target'] = tgt
                        
                        # Load Logs (Optional: Filter by user if you add user col to Sheet1)
                        # For now, we load generic logs
                        log_sheet = get_tab(st.session_state.client, "Sheet1")
                        if log_sheet:
                            st.session_state.food_log = log_sheet.get_all_records()
                            
                        st.success(f"Welcome back, {real_name}!")
                        st.rerun()
                    else:
                        st.error("Incorrect username or password.")
                else:
                    st.error("Cannot connect to database (Offline Mode).")

    with tab2:
        with st.form("signup_form"):
            new_u = st.text_input("New Username")
            new_p = st.text_input("New Password", type="password")
            new_n = st.text_input("Display Name")
            if st.form_submit_button("Sign Up", use_container_width=True):
                if st.session_state.client:
                    success, msg = register_user(new_u, new_p, new_n, st.session_state.client)
                    if success:
                        st.success(msg + " Please log in tab.")
                    else:
                        st.error(msg)
    
    st.stop() # 🛑 STOPS APP HERE IF NOT LOGGED IN

# --- 7. MAIN APPLICATION (After Login) ---

# Sidebar User Info
st.sidebar.markdown(f"### 👤 {st.session_state.real_name}")
if st.sidebar.button("Logout", key="logout"):
    st.session_state.logged_in = False
    st.rerun()
st.sidebar.divider()
nav = st.sidebar.radio("Navigation", ["📝 Daily Tracker", "📊 Analytics", "📅 Planner", "👤 Profile"])

# --- PAGE: DAILY TRACKER ---
if nav == "📝 Daily Tracker":
    st.header("📝 Daily Tracker")
    
    today_str = str(datetime.date.today())
    
    # Filter logs for today
    today_logs = [x for x in st.session_state.food_log if str(x.get('date')) == today_str]
    consumed = sum(entry['cal'] for entry in today_logs)
    target = st.session_state.user_profile.get('target', 2000)
    remaining = target - consumed
    
    # Metric Cards
    c1, c2 = st.columns(2)
    c1.metric("Consumed", f"{consumed}", "kcal")
    c2.metric("Remaining", f"{remaining}", delta_color="normal" if remaining >= 0 else "inverse")
    st.progress(min(consumed/target, 1.0))
    
    st.divider()
    
    # Quick Add
    with st.expander("➕ Add Meal", expanded=True):
        with st.form("add_meal"):
            c_name, c_cal = st.columns([2, 1])
            name = c_name.text_input("Food Name")
            cal = c_cal.number_input("Calories", min_value=0, step=10)
            if st.form_submit_button("Add Entry"):
                new_entry = {'date': today_str, 'name': name, 'cal': cal, 'type': 'Manual'}
                
                # Save to Google Sheet (Sheet1)
                sheet1 = get_tab(st.session_state.client, "Sheet1")
                if sheet1:
                    sheet1.append_row([today_str, name, cal, 'Manual'])
                    st.session_state.food_log.append(new_entry)
                    st.toast(f"Added {name}!")
                    st.rerun()

    # Log Display
    if today_logs:
        st.subheader("Today's History")
        st.dataframe(pd.DataFrame(today_logs)[['name', 'cal', 'type']], use_container_width=True)

# --- PAGE: ANALYTICS (NEW!) ---
elif nav == "📊 Analytics":
    st.header("📊 Progress & Trends")
    
    # Fetch user history from 'profiles' tab
    p_sheet = get_tab(st.session_state.client, "profiles")
    if p_sheet:
        all_records = p_sheet.get_all_records()
        user_records = [r for r in all_records if str(r.get('username')) == st.session_state.username]
        
        if user_records:
            df = pd.DataFrame(user_records)
            df['date'] = pd.to_datetime(df['date'])
            df['weight'] = pd.to_numeric(df['weight'])
            
            # Interactive Date Filter
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
                # Altair Chart
                chart = alt.Chart(filtered_df).mark_line(point=True, color='teal').encode(
                    x=alt.X('date:T', title='Date'),
                    y=alt.Y('weight:Q', scale=alt.Scale(zero=False), title='Weight (kg)'),
                    tooltip=['date', 'weight', 'goal']
                ).properties(height=350)
                st.altair_chart(chart, use_container_width=True)
                
                # Data Table
                st.dataframe(filtered_df[['date', 'weight', 'goal']].sort_values(by='date', ascending=False), use_container_width=True)
            else:
                st.info("No data for this time range.")
        else:
            st.info("No profile history found. Update your profile to start tracking trends!")

# --- PAGE: PLANNER ---
elif nav == "📅 Planner":
    st.header("📅 Smart Meal Planner")
    current_target = st.session_state.user_profile.get('target', 2000)
    st.write(f"Generating plan for target: **{current_target} kcal**")
    
    if st.button("Generate New Plan"):
        plan = []
        total_cal = 0
        # Simple Logic: Pick random meals until target is close
        attempts = 0
        while total_cal < (current_target - 200) and attempts < 10:
            item = FOOD_DB.sample(1).iloc[0]
            plan.append(item.to_dict())
            total_cal += item['cal']
            attempts += 1
        st.session_state.generated_plan = plan
    
    if 'generated_plan' in st.session_state:
        for i, item in enumerate(st.session_state.generated_plan):
            c1, c2 = st.columns([3, 1])
            c1.write(f"**{item['type']}**: {item['name']}")
            c2.write(f"{item['cal']} kcal")

# --- PAGE: PROFILE (UPDATES) ---
elif nav == "👤 Profile":
    st.header("👤 Update Profile")
    st.info("Updating your details here will recalculate your targets and save a history point for analytics.")
    
    curr = st.session_state.user_profile
    
    with st.form("profile_update"):
        c1, c2 = st.columns(2)
        w = c1.number_input("Current Weight (kg)", value=float(curr.get('weight', 70)))
        h = c2.number_input("Height (cm)", value=int(curr.get('height', 170)))
        a = c1.number_input("Age", value=int(curr.get('age', 30)))
        g = c2.selectbox("Gender", ["Male", "Female"], index=0 if curr.get('gender') == 'Male' else 1)
        
        act = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"], index=0)
        goal = st.selectbox("Goal", list(GOAL_DB.keys()), index=0)
        
        if st.form_submit_button("💾 Save & Update"):
            # 1. Calculate New Target
            new_target = calculate_target(w, h, a, g, act, goal)
            
            # 2. Update Session State
            updated_data = {
                'weight': w, 'height': h, 'age': a, 'gender': g,
                'activity': act, 'goal': goal, 'target': new_target
            }
            st.session_state.user_profile = updated_data
            
            # 3. Save History to Google Sheet
            if st.session_state.client:
                save_profile_update(st.session_state.username, updated_data, st.session_state.client)
                st.success(f"Profile updated! New Daily Target: {new_target} kcal")
                # Wait a moment then rerun to refresh target on sidebar
                st.rerun()
