import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(layout="wide")
st.title("🕵️‍♂️ Connection Diagnostic")

# 1. READ SECRETS
st.write("### 1. Checking Secrets...")
if "service_account" not in st.secrets:
    st.error("❌ section '[service_account]' is MISSING in secrets.")
elif "payload" not in st.secrets["service_account"]:
    st.error("❌ key 'payload' is MISSING inside [service_account].")
else:
    st.success("✅ Secrets structure found.")
    
    # 2. PARSE JSON
    try:
        raw_json = st.secrets["service_account"]["payload"]
        key_dict = json.loads(raw_json)
        email = key_dict.get("client_email", "Unknown")
        st.write(f"**Bot Email detected:** `{email}`")
        st.success("✅ JSON parsed successfully.")
        
        # 3. TEST CONNECTION
        st.write("### 2. Testing Google API...")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Auto-fix newlines just in case
        if "\\n" in key_dict["private_key"]:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sheet = client.open("NutriTrack_Data")
        
        st.success(f"🎉 SUCCESS! Connected to sheet: **{sheet.title}**")
        st.balloons()
        
    except Exception as e:
        st.error(f"❌ CONNECTION FAILED: {e}")
        st.write("---")
        st.warning("👇 **COMMON FIXES FOR THIS ERROR:**")
        if "API has not been used" in str(e) or "project" in str(e):
            st.markdown("""
            **The Google Sheets API is disabled.**
            1. Go to [Google Cloud Console](https://console.cloud.google.com/).
            2. Select your project **nutrition-app-483014**.
            3. Search for **"Google Sheets API"** -> Click **Enable**.
            4. Search for **"Google Drive API"** -> Click **Enable**.
            """)
        elif "SpreadsheetNotFound" in str(e):
            st.markdown(f"""
            **The Bot cannot see the file.**
            1. Copy this email: `{email}`
            2. Go to your Google Sheet -> **Share**.
            3. Paste the email and set as **Editor**.
            """)

st.stop() # Stops the rest of the app from running so you can focus on this result
# ---------------------------------------------------------

# --- CONNECT TO GOOGLE SHEETS (TOML METHOD) ---
@st.cache_resource
def get_google_sheet():
    try:
        # Check if the secret exists
        if "service_account" in st.secrets:
            # DIRECTLY ACCESS THE DICT (Streamlit does the work for us)
            # We convert it to a standard dict to be safe
            key_dict = dict(st.secrets["service_account"])
            
            # Safety replacement for newlines (Fixes "Invalid Control Character" errors)
            if "\\n" in key_dict["private_key"]:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            
            creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
            client = gspread.authorize(creds)
            sheet = client.open("NutriTrack_Data").sheet1
            return sheet
        else:
            st.error("❌ Critical: '[service_account]' section not found in Secrets.")
            return None
            
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

# Helper to Load Data
def load_data(sheet):
    try:
        if sheet:
            data = sheet.get_all_records()
            return data if data else []
        return []
    except Exception as e:
        print(f"Error loading data: {e}")
        return []

# Helper to Save Data
def save_entry_to_sheet(sheet, entry):
    """
    Saves a dictionary entry to the Google Sheet.
    Expects dictionary keys: date, name, cal, type
    """
    try:
        if sheet:
            row = [str(entry['date']), entry['name'], entry['cal'], entry['type']]
            sheet.append_row(row)
    except Exception as e:
        st.error(f"Failed to save to cloud: {e}")

# --- 2. DATA: DATABASES ---
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast', 'tags': ['Healthy', 'Carbs']},
    {'name': 'Egg White Omelet', 'cal': 250, 'type': 'Breakfast', 'tags': ['Low Fat', 'High Protein']},
    {'name': 'Keto Avocado Plate', 'cal': 400, 'type': 'Breakfast', 'tags': ['Keto', 'High Fat']},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch', 'tags': ['Low Carb', 'High Protein']},
    {'name': 'Quinoa & Black Beans', 'cal': 500, 'type': 'Lunch', 'tags': ['Vegan', 'High Fiber']},
    {'name': 'Salmon with Asparagus', 'cal': 600, 'type': 'Dinner', 'tags': ['High Protein', 'Healthy Fats']},
    {'name': 'Lean Beef Stir Fry', 'cal': 700, 'type': 'Dinner', 'tags': ['High Protein']},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack', 'tags': ['High Protein']},
    {'name': 'Almonds (30g)', 'cal': 170, 'type': 'Snack', 'tags': ['Keto', 'Healthy Fats']},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack', 'tags': ['Healthy', 'Carbs']}
])

# --- UPDATED GOAL DICTIONARY ---
GOAL_DB = {
    # Weight Management
    "Maintain Current Weight": 0,
    "Lose Weight (Slow & Steady)": -250,
    "Lose Weight (Standard)": -500,
    "Lose Weight (Aggressive)": -750,
    "Weight Gain (Muscle)": 300,
    
    # Fitness & Performance
    "Build Muscle (Lean Bulk)": 300,
    "Build Muscle (Dirty Bulk)": 600,
    "Marathon / Ultra Training": 800,
    "Triathlon Training": 700,
    "Cycling (Endurance)": 600,
    "Swimming (Competitive)": 500,
    "Strength Training / Powerlifting": 400,
    "CrossFit / HIIT Performance": 450,
    
    # Health & Medical
    "Manage Type 2 Diabetes (Low Sugar)": -200,
    "Heart Health (Low Sodium)": -100,
    "PCOS Management": -250,
    "IBS / Low FODMAP": 0,
    "Celiac / Gluten Free": 0,
    
    # Dietary Styles
    "Keto / Low Carb Adaptation": 0,
    "Intermittent Fasting (16:8)": 0,
    "Pregnancy (2nd/3rd Trimester)": 350,
    "Breastfeeding": 500,
    "Improve Energy / Fatigue": 0
}

# --- 3. SESSION STATE INITIALIZATION ---
if 'sheet' not in st.session_state:
    st.session_state.sheet = get_google_sheet()

if 'log' not in st.session_state:
    if st.session_state.sheet:
        loaded = load_data(st.session_state.sheet)
        st.session_state.log = loaded if loaded else []
    else:
        st.session_state.log = []

if 'generated_plan' not in st.session_state: 
    st.session_state.generated_plan = None 

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'name': 'Guest', 'target': 2000, 'goals': ['Maintain Current Weight']}

if 'setup_complete' not in st.session_state: 
    st.session_state.setup_complete = False

# --- 4. CALCULATION LOGIC ---
def calculate_bmr(weight, height, age, gender):
    return (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161

def calculate_bmi(weight, height_cm):
    height_m = height_cm / 100
    bmi = weight / (height_m ** 2)
    if bmi < 18.5: return bmi, "Underweight"
    elif 18.5 <= bmi < 24.9: return bmi, "Healthy Weight"
    elif 25 <= bmi < 29.9: return bmi, "Overweight"
    else: return bmi, "Obese"

def calculate_tdee(bmr, activity_level):
    multipliers = {
        "Sedentary (Office Job)": 1.2,
        "Lightly Active (1-3 days)": 1.375,
        "Moderately Active (3-5 days)": 1.55,
        "Very Active (6-7 days)": 1.725,
        "Athlete (2x per day)": 1.9
    }
    return bmr * multipliers.get(activity_level, 1.2)

def calculate_target_from_goals(tdee, selected_goals, custom_goals_list):
    adjustment = 0
    for goal in selected_goals:
        adjustment += GOAL_DB.get(goal, 0)
    return max(tdee + adjustment, 1200) # Safety floor

def generate_menu(target):
    menu = []
    current_cal = 0
    # Add main meals
    for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
        item = FOOD_DB[FOOD_DB['type'] == meal_type].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    # Add snacks
    attempts = 0
    while current_cal < (target - 100) and attempts < 10:
        item = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
        attempts += 1
    return menu

# --- 5. UI & NAVIGATION ---
st.sidebar.title("📱 Navigation")
page = st.sidebar.radio("Go to", ["👤 Profile & Targets", "📅 Smart Planner", "📝 Daily Tracker", "📊 Dashboard"])
st.sidebar.divider()

# Connection Status Indicator
if st.session_state.sheet:
    st.sidebar.success("🟢 Cloud Sync Active")
else:
    st.sidebar.warning("⚪ Offline Mode")

if st.session_state.setup_complete:
    p = st.session_state.user_profile
    st.sidebar.metric("Target", f"{p['target']:.0f} kcal")
    if 'bmi' in p: 
        st.sidebar.metric("BMI", f"{p['bmi']:.1f}", p['bmi_category'])

# --- PAGE 1: PROFILE ---
if page == "👤 Profile & Targets":
    st.title("👤 User Profile")
    st.info("ℹ️ Clicking 'Save' will record your profile settings to the Google Sheet.")
    
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("First Name", value=st.session_state.user_profile.get('name', ''))
        gender = st.selectbox("Gender", ["Male", "Female"])
        age = st.number_input("Age", 18, 100, 30)
        weight = st.number_input("Weight (kg)", 40, 200, 70)
        height = st.number_input("Height (cm)", 100, 250, 175)
    with c2:
        activity = st.selectbox("Activity Level", ["Sedentary (Office Job)", "Lightly Active (1-3 days)", "Moderately Active (3-5 days)", "Very Active (6-7 days)", "Athlete (2x per day)"])
        st.divider()
        all_options = sorted(list(GOAL_DB.keys()))
        selected_goals = st.multiselect("Select Goals:", all_options, default=["Maintain Current Weight"])
        with st.expander("Custom Goal"):
            custom_input = st.text_input("Goal Name")

    if st.button("💾 Save Profile", type="primary"):
        # 1. Calculations
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        bmi, bmi_cat = calculate_bmi(weight, height)
        final_goals = selected_goals + ([custom_input] if custom_input else [])
        target = calculate_target_from_goals(tdee, selected_goals, [custom_input])
        
        # 2. Update Session State
        st.session_state.user_profile = {
            'name': name, 'bmr': bmr, 'tdee': tdee, 'target': target, 
            'goals': final_goals, 'activity': activity, 'bmi': bmi, 'bmi_category': bmi_cat
        }
        st.session_state.setup_complete = True
        
        # 3. SAVE TO GOOGLE SHEET
        if st.session_state.sheet:
            # We construct a special 'Profile Update' entry
            profile_entry = {
                'date': str(datetime.date.today()),
                'name': f"Profile Update: {name} ({weight}kg)",
                'cal': int(target),
                'type': 'Profile_Settings'
            }
            save_entry_to_sheet(st.session_state.sheet, profile_entry)
            st.toast("Profile saved to Google Sheet!", icon="☁️")
        
        st.balloons()
        st.rerun()

# --- PAGE 2: PLANNER ---
elif page == "📅 Smart Planner":
    st.title("📅 Smart Planner")
    if st.session_state.setup_complete:
        st.subheader(f"Plan for: {st.session_state.user_profile['name']}")
        if st.button("Generate Meal Plan"):
            menu = generate_menu(st.session_state.user_profile['target'])
            st.session_state.generated_plan = menu
            st.rerun()
            
        if st.session_state.generated_plan:
            st.write("### Today's Template")
            for item in st.session_state.generated_plan:
                st.write(f"**{item['type']}**: {item['name']} ({item['cal']} kcal)")
    else:
        st.warning("Please setup your profile first.")

# --- PAGE 3: TRACKER ---
elif page == "📝 Daily Tracker":
    st.title("📝 Daily Tracker")
    
    # 1. ADD FROM PLAN
    if st.session_state.generated_plan:
        with st.expander("Quick Add from Plan", expanded=True):
            cols = st.columns(3)
            for idx, item in enumerate(st.session_state.generated_plan):
                with cols[idx%3]:
                    if st.button(f"+ {item['name']}", key=f"p_{idx}"):
                        new_entry = {'date': str(datetime.date.today()), 'name': item['name'], 'cal': item['cal'], 'type': 'Food'}
                        st.session_state.log.append(new_entry)
                        if st.session_state.sheet:
                            save_entry_to_sheet(st.session_state.sheet, new_entry)
                        st.toast(f"Saved {item['name']} to Cloud")

    st.divider()
    
    # 2. MANUAL ADD
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1: m_name = st.text_input("Manual Item")
    with c2: m_cal = st.number_input("Calories", 0, 3000, 0)
    with c3: 
        if st.button("Add"):
            new_entry = {'date': str(datetime.date.today()), 'name': m_name, 'cal': m_cal, 'type': 'Manual'}
            st.session_state.log.append(new_entry)
            if st.session_state.sheet:
                save_entry_to_sheet(st.session_state.sheet, new_entry)
            st.rerun()

    # 3. SHOW LOG (Filtered for Today)
    today_str = str(datetime.date.today())
    # Ensure log is clean
    safe_log = [x for x in st.session_state.log if isinstance(x, dict)]
    today_data = [x for x in safe_log if str(x.get('date')) == today_str]
    
    if today_data:
        df = pd.DataFrame(today_data)
        st.dataframe(df, use_container_width=True)
        st.metric("Total Today", f"{df['cal'].sum()} kcal")
    else:
        st.info("No logs for today.")

# --- PAGE 4: DASHBOARD ---
elif page == "📊 Dashboard":
    st.title("📊 Analytics")
    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            c = alt.Chart(df).mark_bar().encode(x='date', y='cal', color='type')
            st.altair_chart(c, use_container_width=True)
    else:
        st.info("No data yet.")
