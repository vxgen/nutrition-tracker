import streamlit as st
import pandas as pd
import datetime
import altair as alt
import random

# --- 1. CONFIGURATION & MOCK DATA ---
st.set_page_config(page_title="NutriTrack AI", layout="wide")

# Expanded Mock Database with more options for variety
FOOD_DB = pd.DataFrame([
    # Breakfast
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast'},
    {'name': 'Eggs & Toast', 'cal': 400, 'type': 'Breakfast'},
    {'name': 'Pancakes & Syrup', 'cal': 550, 'type': 'Breakfast'},
    {'name': 'Avocado Toast', 'cal': 320, 'type': 'Breakfast'},
    # Lunch
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch'},
    {'name': 'Tuna Wrap', 'cal': 500, 'type': 'Lunch'},
    {'name': 'Turkey Sandwich', 'cal': 400, 'type': 'Lunch'},
    {'name': 'Quinoa Bowl', 'cal': 480, 'type': 'Lunch'},
    # Dinner
    {'name': 'Steak & Veggies', 'cal': 700, 'type': 'Dinner'},
    {'name': 'Salmon & Rice', 'cal': 650, 'type': 'Dinner'},
    {'name': 'Pasta Bolognese', 'cal': 750, 'type': 'Dinner'},
    {'name': 'Stir Fry Tofu', 'cal': 550, 'type': 'Dinner'},
    # Snack
    {'name': 'Greek Yogurt', 'cal': 150, 'type': 'Snack'},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack'},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack'},
    {'name': 'Almonds (30g)', 'cal': 170, 'type': 'Snack'},
    {'name': 'Banana', 'cal': 105, 'type': 'Snack'}
])

# --- 2. SESSION STATE MANAGEMENT ---
if 'log' not in st.session_state:
    st.session_state.log = [] 
if 'generated_plan' not in st.session_state:
    st.session_state.generated_plan = None 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}

# --- 3. CALCULATIONS & LOGIC ---
def calculate_bmr(weight, height, age, gender):
    # Mifflin-St Jeor Equation
    if gender == 'Male':
        return (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        return (10 * weight) + (6.25 * height) - (5 * age) - 161

def calculate_tdee(bmr, activity_level):
    multipliers = {
        "Sedentary": 1.2,
        "Light Active": 1.375,
        "Moderate Active": 1.55,
        "Very Active": 1.725,
        "Athlete": 1.9
    }
    return bmr * multipliers.get(activity_level, 1.2)

def generate_daily_menu(target_calories):
    """Generates a random menu fitting the calorie budget"""
    menu = []
    current_cal = 0
    
    # Simple logic: 1 Breakfast, 1 Lunch, 1 Dinner, then fill with Snacks
    categories = ['Breakfast', 'Lunch', 'Dinner']
    
    for cat in categories:
        # Pick a random item from the category
        options = FOOD_DB[FOOD_DB['type'] == cat]
        item = options.sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
    
    # Fill remaining space with snacks
    # Prevent infinite loops by capping attempts
    attempts = 0
    while current_cal < (target_calories - 100) and attempts < 10:
        options = FOOD_DB[FOOD_DB['type'] == 'Snack']
        item = options.sample(1).iloc[0].to_dict()
        menu.append(item)
        current_cal += item['cal']
        attempts += 1
        
    return menu, current_cal

# --- 4. UI LAYOUT ---
st.title("🍎 NutriTrack: Planner & Tracker")

tab1, tab2, tab3 = st.tabs(["📅 Smart Planner", "📝 Daily Log", "📊 Dashboard"])

# --- TAB 1: SMART PLANNER ---
with tab1:
    st.header("1. Planner Configuration")
    
    # RESET BUTTON: If the planner looks "stuck", this clears it.
    if st.button("🔄 Reset / Start Over"):
        st.session_state.generated_plan = None
        st.session_state.user_profile = {}
        st.rerun()

    # Input Form
    if st.session_state.generated_plan is None:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Your Stats")
            age = st.number_input("Age", 18, 100, 30)
            gender = st.selectbox("Gender", ["Male", "Female"])
            weight = st.number_input("Weight (kg)", 40, 200, 70)
            height = st.number_input("Height (cm)", 100, 250, 175)
            
        with col2:
            st.subheader("Goals & Plan")
            goal = st.selectbox("Goal", ["Lose Weight", "Maintain Weight", "Build Muscle"])
            activity = st.selectbox("Activity Level (Exercise Frequency)", 
                                    ["Sedentary", "Light Active", "Moderate Active", "Very Active", "Athlete"])
            duration = st.selectbox("Plan Duration", ["1 Week", "1 Month", "1 Quarter", "Half Year", "1 Year"])

        if st.button("GENERATE PLAN"):
            # 1. Math
            bmr = calculate_bmr(weight, height, age, gender)
            tdee = calculate_tdee(bmr, activity)
            
            # 2. Adjust for Goal
            target_cal = tdee
            if goal == "Lose Weight":
                target_cal = tdee - 500
            elif goal == "Build Muscle":
                target_cal = tdee + 300
                
            # 3. Generate Menu
            menu, menu_cal = generate_daily_menu(target_cal)
            
            # 4. Save to State
            st.session_state.user_profile = {
                'bmr': bmr, 'tdee': tdee, 'target': target_cal, 
                'goal': goal, 'duration': duration, 'activity': activity
            }
            st.session_state.generated_plan = menu
            st.rerun()
            
    else:
        # RESULT VIEW (Only shows if plan exists)
        profile = st.session_state.user_profile
        
        st.success(f"✅ Plan Generated: {profile['duration']} for {profile['goal']}")
        
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Daily Calorie Target", f"{profile['target']:.0f} kcal")
        col_b.metric("Base Burn (TDEE)", f"{profile['tdee']:.0f} kcal")
        col_c.metric("Activity Setting", profile['activity'])

        st.divider()

        st.subheader("🍽️ Your Daily Menu")
        st.write("Based on your target, here is a suggested menu plan:")
        
        if st.button("🔀 Shuffle Menu (Get New Suggestions)"):
            menu, menu_cal = generate_daily_menu(profile['target'])
            st.session_state.generated_plan = menu
            st.rerun()

        # Display Menu Items
        for item in st.session_state.generated_plan:
            with st.container():
                c1, c2, c3 = st.columns([2, 4, 2])
                c1.write(f"**{item['type']}**")
                c2.write(item['name'])
                c3.write(f"{item['cal']} kcal")
                
        st.info("💡 Go to the **'Daily Log'** tab to track these meals as you eat them!")

# --- TAB 2: DAILY LOG ---
with tab2:
    st.header("📝 Track Intake")
    
    # 1. Quick Add from Plan
    if st.session_state.generated_plan:
        st.subheader("Fast Add: From Your Plan")
        cols = st.columns(3)
        for idx, item in enumerate(st.session_state.generated_plan):
            with cols[idx % 3]: 
                if st.button(f"+ {item['name']}", key=f"log_{idx}"):
                    st.session_state.log.append({
                        'name': item['name'],
                        'cal': item['cal'],
                        'date': datetime.date.today(),
                        'type': 'Food'
                    })
                    st.success("Added!")

    st.divider()

    # 2. Manual Add
    st.subheader("Manual Add")
    col1, col2 = st.columns(2)
    with col1:
        m_name = st.selectbox("Select Item", FOOD_DB['name'].unique())
    with col2:
        # Find cal for selected item
        ref_cal = FOOD_DB[FOOD_DB['name'] == m_name].iloc[0]['cal']
        m_cal = st.number_input("Calories", value=int(ref_cal))
        
    if st.button("Add Manual Entry"):
        st.session_state.log.append({
            'name': m_name, 
            'cal': m_cal, 
            'date': datetime.date.today(),
            'type': 'Food'
        })
        st.rerun()

    # 3. View Log
    st.subheader("Today's Log")
    today_items = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    
    if today_items:
        df_log = pd.DataFrame(today_items)
        st.table(df_log)
        
        # Calculate totals
        total_eaten = df_log['cal'].sum()
        target = st.session_state.user_profile.get('target', 2000)
        
        st.metric("Total Eaten Today", f"{total_eaten} kcal", f"Target: {target:.0f}")
        st.progress(min(total_eaten / target, 1.0))
    else:
        st.info("No food logged today.")

# --- TAB 3: DASHBOARD ---
with tab3:
    st.header("📊 Your Progress")
    if len(st.session_state.log) > 0:
        df_all = pd.DataFrame(st.session_state.log)
        
        # Simple Bar Chart
        c = alt.Chart(df_all).mark_bar().encode(
            x='date',
            y='cal',
            color='name',
            tooltip=['name', 'cal', 'date']
        )
        st.altair_chart(c, use_container_width=True)
    else:
        st.write("No data yet. Start using the Planner and Daily Log!")
