import streamlit as st
import pandas as pd
import datetime
import altair as alt

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="NutriTrack Pro", layout="wide", initial_sidebar_state="expanded")

# --- 2. DATA: FOOD DATABASE ---
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

# --- 3. DATA: THE MEGA GOAL DICTIONARY ---
GOAL_DB = {
    # --- WEIGHT MANAGEMENT ---
    "Maintain Current Weight": 0,
    "Lose Weight (Slow & Steady)": -250,
    "Lose Weight (Standard)": -500,
    "Lose Weight (Aggressive)": -750,
    "Weight Gain (Slow)": 250,
    "Weight Gain (Fast)": 500,
    
    # --- FITNESS ---
    "Build Muscle (Lean Bulk)": 300,
    "Build Muscle (Dirty Bulk)": 600,
    "Body Recomposition": -200,
    "Strength Training": 400,
    "CrossFit / HIIT Performance": 400,
    
    # --- SPORTS ---
    "Marathon / Ultra Training": 800,
    "Triathlon Training": 700,
    "Cycling (Endurance)": 600,
    "Swimming (Competitive)": 500,
    "Football / Soccer Match Prep": 450,
    "Basketball Performance": 400,
    "Boxing / MMA Training": 500,
    "Yoga / Pilates Lifestyle": 100,
    
    # --- DIETARY & HEALTH ---
    "Keto / Low Carb Adaptation": 0,
    "Intermittent Fasting (16:8)": 0,
    "Manage Type 2 Diabetes (Low Sugar)": -200,
    "Heart Health (Low Sodium)": -100,
    "Pregnancy (2nd/3rd Trimester)": 350,
    "Breastfeeding": 500
}

# --- 4. SESSION STATE ---
if 'log' not in st.session_state: st.session_state.log = [] 
if 'generated_plan' not in st.session_state: st.session_state.generated_plan = None 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {'name': 'Guest', 'target': 2000, 'goals': ['Maintain Current Weight']}
if 'setup_complete' not in st.session_state: st.session_state.setup_complete = False

# --- 5. LOGIC ---
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
    return max(tdee + adjustment, 1200)

def generate_menu(target):
    menu = []
    current_cal = 0
    for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
        item = FOOD_DB[FOOD_DB['type'] == meal_type].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    attempts = 0
    while current_cal < (target - 100) and attempts < 15:
        item = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
        attempts += 1
    return menu

# --- 6. NAVIGATION ---
st.sidebar.title("📱 Navigation")
page = st.sidebar.radio("Go to", ["👤 Profile & Targets", "📅 Smart Planner", "📝 Daily Tracker", "📊 Dashboard"])
st.sidebar.divider()

if st.session_state.setup_complete:
    p = st.session_state.user_profile
    st.sidebar.metric("Daily Target", f"{p['target']:.0f} kcal")
    
    # NEW: Show BMI in Sidebar
    if 'bmi' in p:
        st.sidebar.metric("Your BMI", f"{p['bmi']:.1f}", p['bmi_category'])
    
    st.sidebar.caption("Goals Active: " + str(len(p['goals'])))

# --- PAGE 1: SETUP ---
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
        activity = st.selectbox("Activity Level", ["Sedentary (Office Job)", "Lightly Active (1-3 days)", "Moderately Active (3-5 days)", "Very Active (6-7 days)", "Athlete (2x per day)"])
        
        st.divider()
        st.subheader("3. Smart Goal Search")
        
        all_options = sorted(list(GOAL_DB.keys()))
        selected_goals = st.multiselect("Select your Goals:", all_options, default=["Maintain Current Weight"])
        
        with st.expander("My goal isn't in the list"):
            custom_input = st.text_input("Custom Goal Name")

    st.divider()
    if st.button("💾 Save Profile", type="primary"):
        # 1. Math
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        bmi, bmi_cat = calculate_bmi(weight, height) # NEW: Calculate BMI
        
        # 2. Goals
        final_goals_list = selected_goals
        if custom_input: final_goals_list.append(custom_input)
        target = calculate_target_from_goals(tdee, selected_goals, [custom_input])
        
        # 3. Save
        st.session_state.user_profile = {
            'name': name, 'bmr': bmr, 'tdee': tdee, 'target': target, 
            'goals': final_goals_list, 'activity': activity,
            'bmi': bmi, 'bmi_category': bmi_cat # NEW: Save BMI
        }
        st.session_state.setup_complete = True
        st.balloons()
        st.rerun()

    # Display Results if Saved
    if st.session_state.setup_complete:
        p = st.session_state.user_profile
        
        st.success("Profile Saved Successfully!")
        
        # NEW: BMI Visualizer in Result
        st.subheader("Your Health Stats")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("BMI", f"{p['bmi']:.1f}", p['bmi_category'])
        k2.metric("BMR (Rest)", f"{p['bmr']:.0f} kcal")
        k3.metric("TDEE (Maint)", f"{p['tdee']:.0f} kcal")
        k4.metric("TARGET", f"{p['target']:.0f} kcal", "Daily Goal")

# --- PAGE 2: PLANNER ---
elif page == "📅 Smart Planner":
    st.title("📅 Smart Planner")
    if not st.session_state.setup_complete:
        st.warning("Please complete your profile setup first.")
    else:
        st.subheader(f"Plan for: {st.session_state.user_profile['name']}")
        duration = st.selectbox("Plan Duration", ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year"])
        
        if st.button("Generate Meal Plan"):
            menu = generate_menu(st.session_state.user_profile['target'])
            st.session_state.generated_plan = menu
            st.rerun()

        if st.session_state.generated_plan:
            st.write(f"### Daily Template ({st.session_state.user_profile['target']:.0f} kcal)")
            for item in st.session_state.generated_plan:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(f"**{item['type']}**")
                c2.write(item['name'])
                c3.write(f"{item['cal']} kcal")

# --- PAGE 3: TRACKER ---
elif page == "📝 Daily Tracker":
    st.title("📝 Daily Tracker")
    
    if st.session_state.generated_plan:
        with st.expander("Quick Add from Plan", expanded=True):
            cols = st.columns(3)
            for idx, item in enumerate(st.session_state.generated_plan):
                with cols[idx%3]:
                    if st.button(f"+ {item['name']}", key=f"t_{idx}"):
                        st.session_state.log.append({'name': item['name'], 'cal': item['cal'], 'date': datetime.date.today(), 'type': 'Food'})
                        st.toast(f"Added {item['name']}")
    
    st.divider()
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1: m_name = st.text_input("Manual Entry Name")
    with c2: m_cal = st.number_input("Calories", 0, 2000, 0)
    with c3: 
        if st.button("Add"):
            st.session_state.log.append({'name': m_name, 'cal': m_cal, 'date': datetime.date.today(), 'type': 'Manual'})
            st.rerun()

    today = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    if today:
        df = pd.DataFrame(today)
        st.dataframe(df, use_container_width=True)
        st.metric("Total Today", f"{df['cal'].sum()} kcal")

# --- PAGE 4: DASHBOARD ---
elif page == "📊 Dashboard":
    st.title("📊 Analytics")
    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        c = alt.Chart(df).mark_bar().encode(x='date', y='cal', color='type')
        st.altair_chart(c, use_container_width=True)
    else:
        st.info("Start logging to see data here.")
