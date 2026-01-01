import streamlit as st
import pandas as pd
import datetime
import altair as alt

# --- 1. CONFIGURATION & MOCK DATA ---
st.set_page_config(page_title="NutriTrack AI", layout="wide")

# Expanded Mock Database
FOOD_DB = pd.DataFrame([
    {'name': 'Oatmeal & Berries', 'cal': 350, 'type': 'Breakfast'},
    {'name': 'Eggs & Toast', 'cal': 400, 'type': 'Breakfast'},
    {'name': 'Grilled Chicken Salad', 'cal': 450, 'type': 'Lunch'},
    {'name': 'Tuna Wrap', 'cal': 500, 'type': 'Lunch'},
    {'name': 'Steak & Veggies', 'cal': 700, 'type': 'Dinner'},
    {'name': 'Salmon & Rice', 'cal': 650, 'type': 'Dinner'},
    {'name': 'Greek Yogurt', 'cal': 150, 'type': 'Snack'},
    {'name': 'Protein Shake', 'cal': 180, 'type': 'Snack'},
    {'name': 'Apple', 'cal': 80, 'type': 'Snack'},
    {'name': 'Almonds (30g)', 'cal': 170, 'type': 'Snack'}
])

# --- 2. SESSION STATE ---
if 'log' not in st.session_state:
    st.session_state.log = [] 
if 'generated_plan' not in st.session_state:
    st.session_state.generated_plan = None # Stores the calculated plan
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {}

# --- 3. HELPER FUNCTIONS ---
def calculate_bmr(weight, height, age, gender):
    # Mifflin-St Jeor Equation
    if gender == 'Male':
        return (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        return (10 * weight) + (6.25 * height) - (5 * age) - 161

def calculate_tdee(bmr, activity_level):
    multipliers = {
        "Sedentary (Office job, little exercise)": 1.2,
        "Light (1-3 days/week training)": 1.375,
        "Moderate (3-5 days/week training)": 1.55,
        "Heavy (6-7 days/week training)": 1.725,
        "Athlete (2x per day training)": 1.9
    }
    return bmr * multipliers.get(activity_level, 1.2)

def generate_daily_menu(target_calories):
    """Simple logic to pick meals adding up to target"""
    menu = []
    current_cal = 0
    
    # 1. Pick Breakfast
    bk = FOOD_DB[FOOD_DB['type'] == 'Breakfast'].sample(1).iloc[0]
    menu.append(bk)
    current_cal += bk['cal']
    
    # 2. Pick Lunch
    ln = FOOD_DB[FOOD_DB['type'] == 'Lunch'].sample(1).iloc[0]
    menu.append(ln)
    current_cal += ln['cal']
    
    # 3. Pick Dinner
    dn = FOOD_DB[FOOD_DB['type'] == 'Dinner'].sample(1).iloc[0]
    menu.append(dn)
    current_cal += dn['cal']
    
    # 4. Fill remaining with Snacks
    while current_cal < (target_calories - 100):
        sn = FOOD_DB[FOOD_DB['type'] == 'Snack'].sample(1).iloc[0]
        menu.append(sn)
        current_cal += sn['cal']
        
    return menu, current_cal

# --- 4. MAIN INTERFACE ---
st.title("🍎 NutriTrack: Smart Planner")

tab1, tab2, tab3 = st.tabs(["📅 Smart Planner", "📝 Daily Log", "📊 Dashboard"])

# --- TAB 1: SMART PLANNER (The Major Update) ---
with tab1:
    st.header("1. Create Your Plan")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Your Stats")
        age = st.number_input("Age", 18, 100, 30)
        gender = st.selectbox("Gender", ["Male", "Female"])
        weight = st.number_input("Weight (kg)", 40, 200, 70)
        height = st.number_input("Height (cm)", 100, 250, 175)
        
    with col2:
        st.subheader("Goals & Activity")
        goal = st.selectbox("Goal", ["Lose Weight", "Maintain Weight", "Build Muscle"])
        activity = st.selectbox("Activity Level (Includes your training)", 
                                ["Sedentary (Office job, little exercise)", 
                                 "Light (1-3 days/week training)", 
                                 "Moderate (3-5 days/week training)", 
                                 "Heavy (6-7 days/week training)",
                                 "Athlete (2x per day training)"])
        duration = st.selectbox("Plan Duration", ["1 Week", "1 Month", "1 Quarter", "Half Year", "1 Year"])

    if st.button("GENERATE MY PLAN"):
        # 1. Calculate BMR & TDEE
        bmr = calculate_bmr(weight, height, age, gender)
        tdee = calculate_tdee(bmr, activity)
        
        # 2. Adjust for Goal
        target_cal = tdee
        if goal == "Lose Weight":
            target_cal = tdee - 500 # Standard deficit
        elif goal == "Build Muscle":
            target_cal = tdee + 300 # Standard surplus
            
        # 3. Store in Session
        st.session_state.user_profile = {
            'bmr': bmr, 'tdee': tdee, 'target': target_cal, 
            'goal': goal, 'duration': duration
        }
        
        # 4. Generate Sample Menu
        menu, menu_cal = generate_daily_menu(target_cal)
        st.session_state.generated_plan = menu
        st.rerun()

    st.divider()
    
    # Display the Plan Result
    if st.session_state.generated_plan:
        profile = st.session_state.user_profile
        
        # Summary Box
        st.info(f"""
        **Plan Generated for {profile['goal']}**
        Based on your stats and activity, your body burns approx **{profile['tdee']:.0f} kcal/day**.
        To reach your goal, your daily target is: **{profile['target']:.0f} kcal**.
        """)
        
        st.subheader(f"Your Suggested Daily Menu ({profile['target']:.0f} kcal)")
        
        # Show the menu in a nice clean list
        for item in st.session_state.generated_plan:
            c1, c2, c3 = st.columns([1, 4, 2])
            with c1:
                st.write(f"**{item['type']}**")
            with c2:
                st.write(item['name'])
            with c3:
                st.write(f"{item['cal']} kcal")
                
        # Calendar View (Visualizing the duration)
        st.subheader(f"Plan Calendar ({profile['duration']})")
        
        days_map = {"1 Week": 7, "1 Month": 30, "1 Quarter": 90, "Half Year": 180, "1 Year": 365}
        total_days = days_map.get(profile['duration'], 7)
        
        # Create a mock calendar dataframe
        start_date = datetime.date.today()
        date_list = [start_date + datetime.timedelta(days=x) for x in range(total_days)]
        
        # Visualizing simply as a progress timeline or table
        st.write(f"This plan covers **{total_days} days**. Tick off your meals in the 'Daily Log' tab.")
        
        # Show first 7 days as a preview
        cal_df = pd.DataFrame({
            'Date': date_list[:7],
            'Planned Calories': [profile['target']] * 7,
            'Status': ['Planned'] * 7
        })
        st.table(cal_df)
        if total_days > 7:
            st.caption("...and so on for the rest of the duration.")

# --- TAB 2: DAILY LOG (Execution) ---
with tab2:
    st.header("📝 Track Your Day")
    
    # Pre-fill target from the planner if it exists
    if st.session_state.user_profile:
        target = st.session_state.user_profile.get('target', 2000)
        st.progress(0, text=f"Daily Target: {target:.0f} kcal")
    
    # If a plan is generated, allow "Quick Add"
    if st.session_state.generated_plan:
        st.subheader("Eat from Plan")
        cols = st.columns(len(st.session_state.generated_plan))
        for idx, item in enumerate(st.session_state.generated_plan):
            with cols[idx % 3]: # Wrap around columns
                if st.button(f"Eat {item['name']}", key=f"eat_{idx}"):
                    st.session_state.log.append({
                        'name': item['name'],
                        'cal': item['cal'],
                        'date': datetime.date.today()
                    })
                    st.success(f"Logged {item['name']}")

    st.divider()
    
    st.subheader("Manual Add")
    m_name = st.text_input("Food Name")
    m_cal = st.number_input("Calories", 0, 2000, 0)
    if st.button("Add Manual Entry"):
        st.session_state.log.append({'name': m_name, 'cal': m_cal, 'date': datetime.date.today()})
        st.rerun()

    # Show Today's Log
    today_log = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    if today_log:
        df = pd.DataFrame(today_log)
        st.table(df)
        total = df['cal'].sum()
        st.metric("Total Today", f"{total} kcal")
    
# --- TAB 3: DASHBOARD ---
with tab3:
    st.header("📊 Progress")
    if not st.session_state.log:
        st.write("Start logging food to see data here.")
    else:
        df_all = pd.DataFrame(st.session_state.log)
        # Chart: Calories over time
        c = alt.Chart(df_all).mark_bar().encode(
            x='date',
            y='cal',
            tooltip=['name', 'cal']
        )
        st.altair_chart(c, use_container_width=True)
