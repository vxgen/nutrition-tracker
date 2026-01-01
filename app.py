import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="NutriTrack Pro", layout="wide", initial_sidebar_state="expanded")

# --- 2. MOCK DATABASE (Expanded for diversity) ---
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

# --- 3. SESSION STATE INITIALIZATION ---
if 'log' not in st.session_state:
    st.session_state.log = [] 
if 'generated_plan' not in st.session_state:
    st.session_state.generated_plan = None 
if 'user_profile' not in st.session_state:
    # Default profile to prevent errors
    st.session_state.user_profile = {
        'name': 'Guest', 'bmr': 1500, 'tdee': 2000, 
        'target': 2000, 'goals': ['Maintain Weight']
    }
if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False

# --- 4. LOGIC FUNCTIONS ---
def calculate_bmr(weight, height, age, gender):
    if gender == 'Male':
        return (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        return (10 * weight) + (6.25 * height) - (5 * age) - 161

def calculate_tdee(bmr, activity_level):
    multipliers = {
        "Sedentary (Office Job)": 1.2,
        "Lightly Active (1-3 days/week)": 1.375,
        "Moderately Active (3-5 days/week)": 1.55,
        "Very Active (6-7 days/week)": 1.725,
        "Athlete (2x per day)": 1.9
    }
    return bmr * multipliers.get(activity_level, 1.2)

def calculate_target(tdee, goals):
    """
    Complex logic to adjust calories based on MULTIPLE goals.
    """
    target = tdee
    adjustment = 0
    
    # Cumulative adjustments
    if "Lose Body Fat" in goals:
        adjustment -= 500
    if "Build Muscle Mass" in goals:
        adjustment += 300
    if "Prepare for Marathon/Endurance" in goals:
        adjustment += 400
    if "Extreme Weight Cut (Short Term)" in goals:
        adjustment -= 800
    
    # Sanity checks for conflicting goals (e.g. Lose Fat + Gain Muscle = Recomp)
    if "Lose Body Fat" in goals and "Build Muscle Mass" in goals:
        # Recomposition strategy: Slight deficit only
        adjustment = -200 
        
    final_target = target + adjustment
    return max(final_target, 1200) # Safety floor of 1200 calories

def generate_menu(target):
    """Generates menu based on target calories"""
    menu = []
    current_cal = 0
    
    # Basic structure: 3 meals + snacks
    for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
        item = FOOD_DB[FOOD_DB['type'] == meal_type].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
        
    # Fill remaining with snacks
    while current_cal < (target - 100):
        item = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    return menu

# --- 5. SIDEBAR NAVIGATION & INFO ---
st.sidebar.title("📱 Navigation")
page = st.sidebar.radio("Go to", ["👤 Profile & Targets", "📅 Smart Planner", "📝 Daily Tracker", "📊 Dashboard"])

st.sidebar.divider()

# Persistent User Summary in Sidebar
if st.session_state.setup_complete:
    p = st.session_state.user_profile
    st.sidebar.subheader("🎯 Active Targets")
    st.sidebar.metric("Daily Calorie Goal", f"{p['target']:.0f} kcal")
    st.sidebar.caption(f"Goals: {', '.join(p['goals'])}")
else:
    st.sidebar.warning("Please complete setup in 'Profile & Targets'")

# --- PAGE 1: PROFILE & TARGET SETUP ---
if page == "👤 Profile & Targets":
    st.title("👤 User Profile & Target Setup")
    st.write("Configure your biology and your goals. We will use this to generate your plan.")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Biological Data")
        name = st.text_input("First Name", value=st.session_state.user_profile.get('name', ''))
        gender = st.selectbox("Gender", ["Male", "Female"])
        age = st.number_input("Age", 18, 100, 30)
        weight = st.number_input("Weight (kg)", 40, 200, 70)
        height = st.number_input("Height (cm)", 100, 250, 175)
        
    with col2:
        st.subheader("2. Lifestyle & Activity")
        activity = st.selectbox("Activity Level", [
            "Sedentary (Office Job)",
            "Lightly Active (1-3 days/week)",
            "Moderately Active (3-5 days/week)",
            "Very Active (6-7 days/week)",
            "Athlete (2x per day)"
        ])
        
        st.subheader("3. Select Your Goals (Multi-Select)")
        # Expanded List of Goals
        goal_options = [
            "Lose Body Fat",
            "Maintain Current Weight",
            "Build Muscle Mass",
            "Improve Cardiovascular Health",
            "Prepare for Marathon/Endurance",
            "Ketogenic Adaptation (Low Carb)",
            "Reduce Sugar Intake",
            "Extreme Weight Cut (Short Term)"
        ]
        
        selected_goals = st.multiselect(
            "What do you want to achieve? (Select all that apply)", 
            goal_options,
            default=["Maintain Current Weight"]
        )

    st.divider()
    
    if st.button("💾 Save Profile & Calculate Targets", type="primary"):
        # 1. Calculate BMR & TDEE
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        
        # 2. Calculate Specific Target based on goals
        final_target = calculate_target(tdee, selected_goals)
        
        # 3. Save to Session State
        st.session_state.user_profile = {
            'name': name,
            'bmr': bmr,
            'tdee': tdee,
            'target': final_target,
            'goals': selected_goals,
            'activity': activity
        }
        st.session_state.setup_complete = True
        st.success("Profile Saved! Your targets have been updated on the sidebar.")
        st.balloons()

    # Show Calculation details if saved
    if st.session_state.setup_complete:
        st.info(f"""
        **Calculation Results:**
        * **BMR (Base Metabolic Rate):** {st.session_state.user_profile['bmr']:.0f} kcal (Burned at rest)
        * **TDEE (Maintenance):** {st.session_state.user_profile['tdee']:.0f} kcal (Burned with activity)
        * **Your Goal Target:** **{st.session_state.user_profile['target']:.0f} kcal/day** based on your selected goals.
        """)

# --- PAGE 2: SMART PLANNER ---
elif page == "📅 Smart Planner":
    st.title("📅 Smart Planner")
    
    if not st.session_state.setup_complete:
        st.error("Please go to 'Profile & Targets' page first to set up your goals.")
    else:
        st.write(f"Hello **{st.session_state.user_profile['name']}**, let's build your plan based on your target of **{st.session_state.user_profile['target']:.0f} kcal**.")
        
        col_dur, col_act = st.columns(2)
        with col_dur:
            duration = st.selectbox("Select Plan Duration", ["1 Week", "1 Month", "1 Quarter", "Half Year", "1 Year"])
        
        if st.button("GENERATE / REFRESH PLAN"):
            menu = generate_menu(st.session_state.user_profile['target'])
            st.session_state.generated_plan = menu
            st.success(f"Plan generated for {duration}!")
            
        st.divider()
        
        if st.session_state.generated_plan:
            st.subheader("Your Daily Template")
            st.caption("You can use this template for the duration of your plan. Tracking is done in the 'Daily Tracker' page.")
            
            for item in st.session_state.generated_plan:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(f"**{item['type']}**")
                c2.write(f"{item['name']}")
                c3.write(f"{item['cal']} kcal")
                
            st.info("Tip: If you have specific workout days, you can manually add extra food in the Tracker on those days.")

# --- PAGE 3: DAILY TRACKER ---
elif page == "📝 Daily Tracker":
    st.title("📝 Daily Tracker")
    
    if st.session_state.generated_plan:
        with st.expander("Tick off items from your Plan", expanded=True):
            cols = st.columns(3)
            for idx, item in enumerate(st.session_state.generated_plan):
                with cols[idx % 3]:
                    if st.button(f"Eat {item['name']}", key=f"track_{idx}"):
                        st.session_state.log.append({
                            'name': item['name'],
                            'cal': item['cal'],
                            'date': datetime.date.today(),
                            'type': 'Food'
                        })
                        st.toast(f"Logged {item['name']}!")
    
    st.divider()
    
    st.subheader("Manual Log")
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        m_name = st.selectbox("Food / Activity", list(FOOD_DB['name']) + ["Running", "Gym", "Cycling"])
    with c2:
        m_cal = st.number_input("Calories (Positive for Food, Negative for Exercise)", value=100)
    with c3:
        if st.button("Add"):
            st.session_state.log.append({
                'name': m_name,
                'cal': m_cal,
                'date': datetime.date.today(),
                'type': 'Manual'
            })
            st.rerun()

    # Show Today's Log
    st.subheader("Today's Record")
    today_log = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    
    if today_log:
        df = pd.DataFrame(today_log)
        st.dataframe(df, use_container_width=True)
        
        total = df['cal'].sum()
        target = st.session_state.user_profile.get('target', 2000)
        remaining = target - total
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Consumed", f"{total} kcal")
        m2.metric("Target", f"{target:.0f} kcal")
        m3.metric("Remaining", f"{remaining:.0f} kcal", delta=remaining)
    else:
        st.info("Nothing logged yet today.")

# --- PAGE 4: DASHBOARD ---
elif page == "📊 Dashboard":
    st.title("📊 Analytics")
    if len(st.session_state.log) > 0:
        df = pd.DataFrame(st.session_state.log)
        
        st.subheader("Calorie Intake History")
        chart = alt.Chart(df).mark_bar().encode(
            x='date:T',
            y='cal:Q',
            color='type:N',
            tooltip=['name', 'cal']
        ).interactive()
        st.altair_chart(chart, use_container_width=True)
    else:
        st.write("No data available.")
