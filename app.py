import streamlit as st
import pandas as pd
import datetime
import altair as alt
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- 1. CONFIGURATION & GOOGLE SHEETS SETUP ---
st.set_page_config(page_title="NutriTrack Pro", layout="wide", initial_sidebar_state="expanded")

# --- CONNECT TO GOOGLE SHEETS ---
# We use @st.cache_resource so we don't reconnect every time you click a button
@st.cache_resource
def get_google_sheet():
    # Load credentials from Streamlit Secrets
    try:
        # We parse the JSON string stored in secrets
        key_dict = json.loads(st.secrets["service_account_info"])
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        client = gspread.authorize(creds)
        
        # Open the sheet (Make sure your Google Sheet is exactly named 'NutriTrack_Data')
        sheet = client.open("NutriTrack_Data").sheet1
        return sheet
    except Exception as e:
        st.error(f"⚠️ Error connecting to Google Sheet: {e}")
        return None

# Helper to Load Data
def load_data(sheet):
    try:
        data = sheet.get_all_records()
        if data:
            return data
        else:
            return []
    except:
        return []

# Helper to Save Data
def save_entry_to_sheet(sheet, entry):
    # entry is a dict: {'date': '...', 'name': '...', 'cal': 123, 'type': '...'}
    try:
        # Convert date to string for JSON serialization
        row = [str(entry['date']), entry['name'], entry['cal'], entry['type']]
        sheet.append_row(row)
    except Exception as e:
        st.error(f"Failed to save to cloud: {e}")

# --- 2. DATA: FOOD DATABASE ---
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast', 'tags': ['Healthy']},
    {'name': 'Egg White Omelet', 'cal': 250, 'type': 'Breakfast', 'tags': ['Protein']},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch', 'tags': ['Low Carb']},
    {'name': 'Quinoa & Black Beans', 'cal': 500, 'type': 'Lunch', 'tags': ['Vegan']},
    {'name': 'Salmon with Asparagus', 'cal': 600, 'type': 'Dinner', 'tags': ['Healthy Fats']},
    {'name': 'Lean Beef Stir Fry', 'cal': 700, 'type': 'Dinner', 'tags': ['High Protein']},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack', 'tags': ['High Protein']},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack', 'tags': ['Fruit']}
])

GOAL_DB = {
    "Maintain Current Weight": 0, "Lose Weight (Standard)": -500,
    "Build Muscle (Lean Bulk)": 300, "Marathon Training": 800
}

# --- 3. SESSION STATE ---
if 'sheet' not in st.session_state:
    st.session_state.sheet = get_google_sheet()

# Load historical data immediately
if 'log' not in st.session_state:
    if st.session_state.sheet:
        st.session_state.log = load_data(st.session_state.sheet)
    else:
        st.session_state.log = []

if 'generated_plan' not in st.session_state: st.session_state.generated_plan = None 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'name': 'Guest', 'target': 2000, 'goals': ['Maintain Current Weight']}
if 'setup_complete' not in st.session_state: st.session_state.setup_complete = False

# --- 4. LOGIC FUNCTIONS ---
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
    multipliers = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725, "Athlete": 1.9}
    return bmr * multipliers.get(activity_level, 1.2)

def calculate_target_from_goals(tdee, selected_goals, custom_goals_list):
    adjustment = 0
    for goal in selected_goals:
        adjustment += GOAL_DB.get(goal, 0)
    return max(tdee + adjustment, 1200)

def generate_menu(target):
    menu = []
    current_cal = 0
    for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
        item = FOOD_DB[FOOD_DB['type'] == meal_type].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    while current_cal < (target - 100):
        item = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    return menu

# --- 5. UI & NAVIGATION ---
st.sidebar.title("📱 Navigation")
page = st.sidebar.radio("Go to", ["👤 Profile & Targets", "📅 Smart Planner", "📝 Daily Tracker", "📊 Dashboard"])
st.sidebar.divider()

if st.session_state.setup_complete:
    p = st.session_state.user_profile
    st.sidebar.metric("Target", f"{p['target']:.0f} kcal")
    if 'bmi' in p: st.sidebar.metric("BMI", f"{p['bmi']:.1f}", p['bmi_category'])

# --- PAGE 1: PROFILE ---
if page == "👤 Profile & Targets":
    st.title("👤 User Profile")
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("First Name", value=st.session_state.user_profile.get('name', ''))
        gender = st.selectbox("Gender", ["Male", "Female"])
        age = st.number_input("Age", 18, 100, 30)
        weight = st.number_input("Weight (kg)", 40, 200, 70)
        height = st.number_input("Height (cm)", 100, 250, 175)
    with c2:
        activity = st.selectbox("Activity Level", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active", "Athlete"])
        st.divider()
        all_options = sorted(list(GOAL_DB.keys()))
        selected_goals = st.multiselect("Select Goals:", all_options, default=["Maintain Current Weight"])
        with st.expander("Custom Goal"):
            custom_input = st.text_input("Goal Name")

    if st.button("💾 Save Profile", type="primary"):
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        bmi, bmi_cat = calculate_bmi(weight, height)
        final_goals = selected_goals + ([custom_input] if custom_input else [])
        target = calculate_target_from_goals(tdee, selected_goals, [custom_input])
        
        st.session_state.user_profile = {
            'name': name, 'bmr': bmr, 'tdee': tdee, 'target': target, 
            'goals': final_goals, 'activity': activity, 'bmi': bmi, 'bmi_category': bmi_cat
        }
        st.session_state.setup_complete = True
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
            for item in st.session_state.generated_plan:
                st.write(f"**{item['type']}**: {item['name']} ({item['cal']} kcal)")
    else:
        st.warning("Setup Profile First")

# --- PAGE 3: TRACKER ---
elif page == "📝 Daily Tracker":
    st.title("📝 Daily Tracker")
    
    # 1. ADD FROM PLAN
    if st.session_state.generated_plan:
        with st.expander("Add from Plan", expanded=True):
            cols = st.columns(3)
            for idx, item in enumerate(st.session_state.generated_plan):
                with cols[idx%3]:
                    if st.button(f"+ {item['name']}", key=f"p_{idx}"):
                        new_entry = {'date': str(datetime.date.today()), 'name': item['name'], 'cal': item['cal'], 'type': 'Food'}
                        st.session_state.log.append(new_entry)
                        # SAVE TO GOOGLE SHEET
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
            # SAVE TO GOOGLE SHEET
            if st.session_state.sheet:
                save_entry_to_sheet(st.session_state.sheet, new_entry)
            st.rerun()

    # 3. SHOW LOG (Filtered for Today)
    today_str = str(datetime.date.today())
    
    # Ensure log is a list of dicts (handle potential loading errors)
    safe_log = [x for x in st.session_state.log if isinstance(x, dict)]
    today_data = [x for x in safe_log if str(x.get('date')) == today_str]
    
    if today_data:
        df = pd.DataFrame(today_data)
        st.dataframe(df)
        st.metric("Total Today", f"{df['cal'].sum()} kcal")
    else:
        st.info("No logs for today.")

# --- PAGE 4: DASHBOARD ---
elif page == "📊 Dashboard":
    st.title("📊 Analytics")
    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        # Ensure date column is datetime for charting
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            c = alt.Chart(df).mark_bar().encode(x='date', y='cal', color='type')
            st.altair_chart(c, use_container_width=True)
    else:
        st.info("No data yet.")
