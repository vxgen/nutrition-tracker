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

# --- 3. DATA: SMART GOAL DATABASE ---
# Format: "Goal Name": Calorie Adjustment (Daily)
GOAL_DB = {
    # Weight Loss
    "Maintain Current Weight": 0,
    "Slow Weight Loss (-0.25kg/week)": -250,
    "Standard Weight Loss (-0.5kg/week)": -500,
    "Aggressive Weight Loss (-1kg/week)": -1000,
    "Summer Cut (Definition)": -400,
    
    # Muscle & Strength
    "Lean Bulk (Muscle w/o Fat)": 250,
    "Dirty Bulk (Max Mass)": 500,
    "Strength Training Support": 300,
    "Muscle Toning": -100, # Slight deficit for definition
    
    # Performance / Athletic
    "Marathon/Triathlon Training": 600,
    "HIIT / Crossfit Fuel": 350,
    "Sports Performance (Match Day)": 400,
    "Recovery Mode (Post-Injury)": 100,
    
    # Health & Dietary
    "Keto Adaptation": 0,
    "Low Carb / High Fat": 0,
    "Intermittent Fasting (16:8)": 0,
    "Heart Health (Low Sodium)": 0,
    "Pregnancy (2nd/3rd Trimester)": 300,
    "Breastfeeding": 500
}

# --- 4. SESSION STATE ---
if 'log' not in st.session_state:
    st.session_state.log = [] 
if 'generated_plan' not in st.session_state:
    st.session_state.generated_plan = None 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        'name': 'Guest', 'target': 2000, 'goals': ['Maintain Current Weight']
    }
if 'setup_complete' not in st.session_state:
    st.session_state.setup_complete = False

# --- 5. LOGIC FUNCTIONS ---
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

def calculate_target_from_goals(tdee, selected_goals):
    adjustment = 0
    # Sum up adjustments from the DB
    for goal in selected_goals:
        if goal in GOAL_DB:
            adjustment += GOAL_DB[goal]
            
    final = tdee + adjustment
    return max(final, 1200) # Safety floor

def generate_menu(target):
    menu = []
    current_cal = 0
    # 3 Meals
    for meal_type in ['Breakfast', 'Lunch', 'Dinner']:
        item = FOOD_DB[FOOD_DB['type'] == meal_type].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    # Snacks to fill gap
    attempts = 0
    while current_cal < (target - 100) and attempts < 10:
        item = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
        attempts += 1
    return menu

# --- 6. SIDEBAR NAVIGATION ---
st.sidebar.title("📱 Navigation")
page = st.sidebar.radio("Go to", ["👤 Profile & Targets", "📅 Smart Planner", "📝 Daily Tracker", "📊 Dashboard"])

st.sidebar.divider()
if st.session_state.setup_complete:
    p = st.session_state.user_profile
    st.sidebar.subheader("🎯 Active Targets")
    st.sidebar.metric("Target", f"{p['target']:.0f} kcal")
    st.sidebar.caption(f"Goals: {len(p['goals'])} selected")
else:
    st.sidebar.warning("⚠ Setup Required")

# --- PAGE 1: PROFILE & TARGET SETUP ---
if page == "👤 Profile & Targets":
    st.title("👤 User Profile & Target Setup")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Stats")
        name = st.text_input("First Name", value=st.session_state.user_profile.get('name', ''))
        gender = st.selectbox("Gender", ["Male", "Female"])
        age = st.number_input("Age", 18, 100, 30)
        weight = st.number_input("Weight (kg)", 40, 200, 70)
        height = st.number_input("Height (cm)", 100, 250, 175)
        
    with col2:
        st.subheader("2. Activity")
        activity = st.selectbox("Activity Level", [
            "Sedentary (Office Job)", "Lightly Active (1-3 days/week)", 
            "Moderately Active (3-5 days/week)", "Very Active (6-7 days/week)", "Athlete (2x per day)"
        ])
        
        st.divider()
        st.subheader("3. Select Your Goals")
        st.info("💡 Type in the box below to search. You can select multiple goals.")
        
        # KEY CHANGE: Using the Keys from GOAL_DB provides 30+ predictive options
        options_list = list(GOAL_DB.keys())
        
        selected_goals = st.multiselect(
            "Search or Select Goals:", 
            options_list,
            default=["Maintain Current Weight"],
            help="Start typing (e.g., 'Muscle', 'Loss', 'Run') to filter options."
        )
        
        # KEY CHANGE: Custom Goal Input
        st.markdown("**Goal not in the list?**")
        custom_goal = st.text_input("Enter a custom goal (optional)")
        
        if custom_goal and custom_goal not in selected_goals:
            # We treat custom goals as neutral (0 cal adjustment) unless user specifies otherwise (advanced)
            selected_goals.append(custom_goal)
            st.caption(f"Added custom goal: '{custom_goal}' (Note: Custom goals don't auto-adjust calories)")

    st.divider()
    
    if st.button("💾 Save Profile & Calculate", type="primary"):
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        final_target = calculate_target_from_goals(tdee, selected_goals)
        
        st.session_state.user_profile = {
            'name': name, 'bmr': bmr, 'tdee': tdee,
            'target': final_target, 'goals': selected_goals, 'activity': activity
        }
        st.session_state.setup_complete = True
        st.success("Profile Updated Successfully!")

    if st.session_state.setup_complete:
        st.success(f"**Target Calculated:** {st.session_state.user_profile['target']:.0f} kcal")

# --- PAGE 2: SMART PLANNER ---
elif page == "📅 Smart Planner":
    st.title("📅 Smart Planner")
    if not st.session_state.setup_complete:
        st.error("Please configure your goals in the Profile page first.")
    else:
        st.write(f"Plan for: **{', '.join(st.session_state.user_profile['goals'])}**")
        duration = st.selectbox("Duration", ["1 Week", "1 Month", "3 Months", "6 Months", "1 Year"])
        
        if st.button("Generate Plan Template"):
            menu = generate_menu(st.session_state.user_profile['target'])
            st.session_state.generated_plan = menu
            st.rerun()

        if st.session_state.generated_plan:
            st.subheader("Daily Menu Template")
            for item in st.session_state.generated_plan:
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(f"**{item['type']}**")
                c2.write(item['name'])
                c3.write(f"{item['cal']} kcal")

# --- PAGE 3: DAILY TRACKER ---
elif page == "📝 Daily Tracker":
    st.title("📝 Daily Tracker")
    
    # Plan Checklist
    if st.session_state.generated_plan:
        with st.expander("Tick off from Plan", expanded=True):
            cols = st.columns(3)
            for idx, item in enumerate(st.session_state.generated_plan):
                with cols[idx%3]:
                    if st.button(f"Eat {item['name']}", key=f"t_{idx}"):
                        st.session_state.log.append({
                            'name': item['name'], 'cal': item['cal'], 
                            'date': datetime.date.today(), 'type': 'Food'
                        })
                        st.toast(f"Logged {item['name']}")
    
    st.divider()
    
    # Manual Input
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1: m_name = st.text_input("Manual Food/Exercise Name")
    with c2: m_cal = st.number_input("Calories (+Food / -Exercise)", value=0)
    with c3: 
        if st.button("Add Log"):
            st.session_state.log.append({
                'name': m_name, 'cal': m_cal, 
                'date': datetime.date.today(), 'type': 'Manual'
            })
            st.rerun()

    # View Logs
    today = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    if today:
        df = pd.DataFrame(today)
        st.dataframe(df)
        st.metric("Total Today", f"{df['cal'].sum()} kcal", f"Target: {st.session_state.user_profile.get('target', 2000):.0f}")

# --- PAGE 4: DASHBOARD ---
elif page == "📊 Dashboard":
    st.title("📊 Analytics")
    if st.session_state.log:
        df = pd.DataFrame(st.session_state.log)
        c = alt.Chart(df).mark_bar().encode(x='date', y='cal', color='type')
        st.altair_chart(c, use_container_width=True)
    else:
        st.info("No data yet.")
