import streamlit as st
import pandas as pd
import datetime
import altair as alt
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="NutriTrack Pro", 
    layout="wide", 
    initial_sidebar_state="collapsed" # Collapsed looks better on mobile initially
)

# Custom CSS for Mobile Friendliness
st.markdown("""
<style>
    /* Make metrics stand out on mobile */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    /* Add some padding to the main area */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# --- CONNECT TO GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    try:
        if "service_account" in st.secrets:
            key_dict = dict(st.secrets["service_account"])
            if "\\n" in key_dict["private_key"]:
                key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
            
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
            client = gspread.authorize(creds)
            sheet = client.open("NutriTrack_Data").sheet1
            return sheet
        else:
            return None
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return None

def load_data(sheet):
    try:
        if sheet:
            data = sheet.get_all_records()
            return data if data else []
        return []
    except:
        return []

def save_entry_to_sheet(sheet, entry):
    try:
        if sheet:
            row = [str(entry['date']), entry['name'], entry['cal'], entry['type']]
            sheet.append_row(row)
    except Exception as e:
        st.error(f"Save failed: {e}")

# --- 2. DATABASES ---
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast'},
    {'name': 'Egg White Omelet', 'cal': 250, 'type': 'Breakfast'},
    {'name': 'Keto Avocado Plate', 'cal': 400, 'type': 'Breakfast'},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch'},
    {'name': 'Quinoa & Black Beans', 'cal': 500, 'type': 'Lunch'},
    {'name': 'Salmon with Asparagus', 'cal': 600, 'type': 'Dinner'},
    {'name': 'Lean Beef Stir Fry', 'cal': 700, 'type': 'Dinner'},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack'},
    {'name': 'Almonds (30g)', 'cal': 170, 'type': 'Snack'},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack'}
])

GOAL_DB = {
    "Maintain Current Weight": 0,
    "Lose Weight (Standard)": -500,
    "Lose Weight (Aggressive)": -750,
    "Build Muscle": 300,
    "Manage Type 2 Diabetes": -200,
    "Heart Health": -100
}

# --- 3. SESSION STATE ---
if 'sheet' not in st.session_state:
    st.session_state.sheet = get_google_sheet()

if 'log' not in st.session_state:
    if st.session_state.sheet:
        loaded = load_data(st.session_state.sheet)
        st.session_state.log = loaded if loaded else []
    else:
        st.session_state.log = []

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'name': 'Guest', 'target': 2000, 'goals': ['Maintain']}

if 'setup_complete' not in st.session_state: 
    st.session_state.setup_complete = False

# --- 4. CALCULATIONS ---
def calculate_bmr(weight, height, age, gender):
    return (10 * weight) + (6.25 * height) - (5 * age) + 5 if gender == 'Male' else (10 * weight) + (6.25 * height) - (5 * age) - 161

def calculate_tdee(bmr, activity):
    levels = {"Sedentary": 1.2, "Lightly Active": 1.375, "Moderately Active": 1.55, "Very Active": 1.725}
    return bmr * levels.get(activity, 1.2)

# --- 5. VISUALIZATION FUNCTIONS ---
def plot_trend(df):
    # Group by Date
    daily = df.groupby('date')['cal'].sum().reset_index()
    chart = alt.Chart(daily).mark_area(
        line={'color':'#4c78a8'},
        color=alt.Gradient(
            gradient='linear',
            stops=[alt.GradientStop(color='white', offset=0),
                   alt.GradientStop(color='#4c78a8', offset=1)],
            x1=1, x2=1, y1=1, y2=0
        )
    ).encode(
        x=alt.X('date:T', title='Date'),
        y=alt.Y('cal:Q', title='Calories'),
        tooltip=['date:T', 'cal']
    ).properties(height=300)
    return chart

def plot_breakdown(df):
    chart = alt.Chart(df).mark_arc(innerRadius=50).encode(
        theta=alt.Theta("cal", stack=True),
        color=alt.Color("type"),
        tooltip=['type', 'cal', 'name']
    ).properties(height=300)
    return chart

# --- 6. UI & NAVIGATION ---
st.sidebar.title("📱 Menu")
page = st.sidebar.radio("Go to", ["📝 Daily Tracker", "📊 Dashboard", "📅 Smart Planner", "👤 Profile"])
st.sidebar.divider()

if st.session_state.sheet:
    st.sidebar.success("🟢 Online")
else:
    st.sidebar.warning("⚪ Offline")

# --- PAGE: DAILY TRACKER (Mobile Optimized) ---
if page == "📝 Daily Tracker":
    st.header("📝 Daily Tracker")
    
    # 1. TOP METRICS (Crucial for Mobile)
    today_str = str(datetime.date.today())
    safe_log = [x for x in st.session_state.log if isinstance(x, dict)]
    today_data = [x for x in safe_log if str(x.get('date')) == today_str]
    
    total_today = sum([x['cal'] for x in today_data])
    target = st.session_state.user_profile['target']
    remaining = target - total_today
    
    # Big visual metric cards
    m1, m2 = st.columns(2)
    m1.metric("Consumed", f"{total_today} kcal")
    m2.metric("Remaining", f"{remaining} kcal", delta_color="normal" if remaining > 0 else "inverse")
    
    # Progress Bar
    progress = min(total_today / target, 1.0)
    st.progress(progress)
    
    st.divider()

    # 2. QUICK ADD
    st.subheader("Add Food")
    with st.form("quick_add"):
        c1, c2 = st.columns([2, 1])
        with c1: name = st.text_input("Food Name", placeholder="e.g. Banana")
        with c2: cal = st.number_input("Kcal", step=10)
        
        submitted = st.form_submit_button("➕ Add Entry", use_container_width=True)
        if submitted and name:
            new_entry = {'date': today_str, 'name': name, 'cal': cal, 'type': 'Manual'}
            st.session_state.log.append(new_entry)
            if st.session_state.sheet:
                save_entry_to_sheet(st.session_state.sheet, new_entry)
            st.rerun()

    # 3. HISTORY TABLE
    if today_data:
        st.subheader("Today's Log")
        df = pd.DataFrame(today_data)
        st.dataframe(
            df[['name', 'cal', 'type']], 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("No meals logged today.")

# --- PAGE: DASHBOARD (Visuals) ---
elif page == "📊 Dashboard":
    st.header("📊 Analytics Dashboard")
    
    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        # Filter out Profile updates so they don't mess up the charts
        df = df[df['type'] != 'Profile_Settings']
        
        if not df.empty:
            tab1, tab2 = st.tabs(["📈 Trends", "🥧 Habits"])
            
            with tab1:
                st.subheader("Calorie Intake Over Time")
                st.altair_chart(plot_trend(df), use_container_width=True)
                
            with tab2:
                st.subheader("What do you eat most?")
                st.altair_chart(plot_breakdown(df), use_container_width=True)
        else:
            st.info("Not enough food data to show charts.")
    else:
        st.info("Start logging food to see your analytics!")

# --- PAGE: PROFILE ---
elif page == "👤 Profile":
    st.header("👤 Your Settings")
    
    with st.form("profile_form"):
        name = st.text_input("Name", value=st.session_state.user_profile.get('name', ''))
        c1, c2 = st.columns(2)
        with c1: 
            weight = st.number_input("Weight (kg)", value=70)
            age = st.number_input("Age", value=30)
        with c2: 
            height = st.number_input("Height (cm)", value=170)
            gender = st.selectbox("Gender", ["Male", "Female"])
            
        activity = st.selectbox("Activity", ["Sedentary", "Lightly Active", "Moderately Active", "Very Active"])
        goal = st.selectbox("Main Goal", list(GOAL_DB.keys()))
        
        if st.form_submit_button("Update Profile", use_container_width=True):
            bmr = calculate_bmr(weight, height, age, gender)
            tdee = calculate_tdee(bmr, activity)
            target = max(1200, tdee + GOAL_DB[goal])
            
            st.session_state.user_profile.update({
                'name': name, 'target': target, 'goals': [goal]
            })
            st.session_state.setup_complete = True
            
            # Save to Cloud
            if st.session_state.sheet:
                entry = {'date': str(datetime.date.today()), 'name': f"Profile: {name}", 'cal': int(target), 'type': 'Profile_Settings'}
                save_entry_to_sheet(st.session_state.sheet, entry)
                
            st.success("Profile Updated!")
            st.rerun()

# --- PAGE: PLANNER ---
elif page == "📅 Smart Planner":
    st.header("📅 Meal Planner")
    if st.button("🎲 Generate Random Plan", use_container_width=True):
        # Simple random generation
        plan = []
        total = 0
        target = st.session_state.user_profile['target']
        
        # Pick 3 random meals
        for _ in range(3):
            item = FOOD_DB.sample(1).iloc[0]
            plan.append(item.to_dict())
            total += item['cal']
            
        st.session_state.generated_plan = plan
        
    if st.session_state.get('generated_plan'):
        for item in st.session_state.generated_plan:
            c1, c2, c3 = st.columns([3,1,1])
            c1.write(f"**{item['name']}**")
            c2.write(f"{item['cal']} kcal")
            if c3.button("Add", key=item['name']):
                new = {'date': str(datetime.date.today()), 'name': item['name'], 'cal': item['cal'], 'type': item['type']}
                st.session_state.log.append(new)
                if st.session_state.sheet:
                    save_entry_to_sheet(st.session_state.sheet, new)
                st.toast(f"Added {item['name']}")
