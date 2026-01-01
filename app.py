import streamlit as st
import pandas as pd
import datetime
import altair as alt

# --- 1. CONFIGURATION & MOCK DATA ---
st.set_page_config(page_title="NutriTrack", layout="wide")

# Mock Database for Food (In a real app, this would be a SQL DB or API)
FOOD_DB = pd.DataFrame({
    'name': ['Apple', 'Banana', 'Chicken Breast', 'Rice (White)', 'Broccoli', 'Egg', 'Milk', 'Salad', 'Protein Shake', 'Pizza Slice', 'Soda'],
    'calories_per_100g': [52, 89, 165, 130, 34, 155, 42, 33, 120, 266, 41],
    'type': ['Food', 'Food', 'Food', 'Food', 'Food', 'Food', 'Drink', 'Food', 'Drink', 'Food', 'Drink']
})

# Mock Database for Exercise (MET values approx)
EXERCISE_DB = {
    'Running (moderate)': 8.0,
    'Walking (brisk)': 4.0,
    'Cycling': 6.0,
    'Weight Lifting': 3.5,
    'Yoga': 2.5,
    'Swimming': 7.0
}

# --- 2. SESSION STATE SETUP (To hold data while app runs) ---
if 'log' not in st.session_state:
    st.session_state.log = [] # List of dictionaries
if 'user_targets' not in st.session_state:
    st.session_state.user_targets = {'daily': 2000, 'goal': 'Maintain Weight'}
if 'plan' not in st.session_state:
    st.session_state.plan = [] # Items planned for the day

# --- 3. HELPER FUNCTIONS ---
def convert_cal_to_kj(cal):
    return cal * 4.184

def get_calories(food_name, amount_g):
    food = FOOD_DB[FOOD_DB['name'] == food_name].iloc[0]
    return (food['calories_per_100g'] * amount_g) / 100

def suggest_food(calories_left):
    """Simple logic to suggest food based on remaining budget"""
    if calories_left <= 0:
        return []
    # Find foods where a 100g serving fits the budget
    options = FOOD_DB[FOOD_DB['calories_per_100g'] <= calories_left]
    return options['name'].tolist()

# --- 4. SIDEBAR: SETTINGS & TARGETS ---
st.sidebar.header("⚙️ User Settings")

# Unit Preference
unit = st.sidebar.radio("Preferred Unit", ["Calories (kcal)", "Kilojoules (kJ)"])

# Goal Setting
st.sidebar.subheader("Set Targets")
goal_type = st.sidebar.selectbox("Goal", ["Lose Weight", "Maintain Weight", "Gain Muscle"])
daily_target = st.sidebar.number_input("Daily Target (kcal)", value=st.session_state.user_targets['daily'])
st.session_state.user_targets = {'daily': daily_target, 'goal': goal_type}

# Calculate Weekly/Monthly targets automatically
weekly_target = daily_target * 7
monthly_target = daily_target * 30

# --- 5. MAIN INTERFACE ---
st.title("🍎 NutriTrack: Daily Nutrition & Fitness")

# Tabs for major functionalities
tab1, tab2, tab3, tab4 = st.tabs(["📝 Daily Log", "📅 Planner", "📊 Overview & Insights", "🏃 Fitness Calculator"])

# --- TAB 1: DAILY LOG (Inputs for Food) ---
with tab1:
    st.subheader("Log your Intake")
    
    col1, col2 = st.columns(2)
    with col1:
        # Dropdown with predictive typing (Streamlit handles filtering automatically)
        food_choice = st.selectbox("Select Food/Drink", FOOD_DB['name'].unique())
    with col2:
        amount = st.number_input("Amount (grams or ml)", min_value=1, value=100)
    
    if st.button("Add Intake"):
        cals = get_calories(food_choice, amount)
        st.session_state.log.append({
            'type': 'Intake',
            'name': food_choice,
            'amount': amount,
            'calories': cals,
            'date': datetime.date.today()
        })
        st.success(f"Added {food_choice}!")

    st.divider()
    
    # Tick off from Plan Logic
    if st.session_state.plan:
        st.subheader("Tick off from Plan")
        for i, item in enumerate(st.session_state.plan):
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.write(f"Planned: {item['name']} ({item['amount']}g)")
            with col_b:
                if st.button("Eat", key=f"plan_{i}"):
                    cals = get_calories(item['name'], item['amount'])
                    st.session_state.log.append({
                        'type': 'Intake',
                        'name': item['name'],
                        'amount': item['amount'],
                        'calories': cals,
                        'date': datetime.date.today()
                    })
                    st.session_state.plan.pop(i)
                    st.rerun()

    # Display Today's Log
    st.subheader("Today's Record")
    today_log = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    if today_log:
        df_log = pd.DataFrame(today_log)
        if unit == "Kilojoules (kJ)":
            df_log['Energy (kJ)'] = df_log['calories'].apply(convert_cal_to_kj)
            st.table(df_log[['type', 'name', 'amount', 'Energy (kJ)']])
        else:
            st.table(df_log[['type', 'name', 'amount', 'calories']])
    else:
        st.info("No records for today yet.")

# --- TAB 2: PLANNER ---
with tab2:
    st.subheader("Plan Your Meals")
    st.write("Add items here to build a plan. They won't count as intake until you 'Tick them off' in the Daily Log.")
    
    p_food = st.selectbox("Plan Food", FOOD_DB['name'].unique(), key="plan_sel")
    p_amount = st.number_input("Plan Amount (g)", min_value=1, value=100, key="plan_amt")
    
    if st.button("Add to Plan"):
        st.session_state.plan.append({'name': p_food, 'amount': p_amount})
        st.success("Added to plan!")
        
    st.write("Current Plan:")
    st.write(st.session_state.plan)

# --- TAB 3: OVERVIEW & INSIGHTS ---
with tab3:
    st.subheader("Energy Balance Dashboard")
    
    # Calculate totals
    today_items = [x for x in st.session_state.log if x['date'] == datetime.date.today()]
    
    total_intake = sum([x['calories'] for x in today_items if x['type'] == 'Intake'])
    total_burn = sum([x['calories'] for x in today_items if x['type'] == 'Exercise'])
    net_calories = total_intake - total_burn
    
    remaining = daily_target - net_calories
    
    # Metrics Row
    m1, m2, m3 = st.columns(3)
    
    display_intake = total_intake * 4.184 if unit == "Kilojoules (kJ)" else total_intake
    display_target = daily_target * 4.184 if unit == "Kilojoules (kJ)" else daily_target
    display_rem = remaining * 4.184 if unit == "Kilojoules (kJ)" else remaining
    label_unit = "kJ" if unit == "Kilojoules (kJ)" else "kcal"

    m1.metric("Total Intake", f"{display_intake:.0f} {label_unit}")
    m2.metric("Target", f"{display_target:.0f} {label_unit}")
    m3.metric("Remaining", f"{display_rem:.0f} {label_unit}", delta_color="normal")
    
    # Progress Bar
    st.write("Daily Progress")
    progress = min(total_intake / daily_target, 1.0) if daily_target > 0 else 0
    st.progress(progress)
    
    st.divider()
    
    # Suggestions
    st.subheader("💡 Suggestions")
    if remaining > 0:
        st.info(f"You have energy left! Based on your remaining budget ({remaining:.0f} kcal), you could eat:")
        suggestions = suggest_food(remaining)
        if suggestions:
            st.write(", ".join(suggestions))
        else:
            st.write("Small snack (e.g., an apple or salad).")
    elif remaining < 0:
        st.warning("You have exceeded your daily target. Consider a light walk or reducing intake tomorrow.")

    # Charts (Simple Altair Chart)
    st.subheader("Target vs Actual")
    chart_data = pd.DataFrame({
        'Category': ['Intake', 'Target', 'Remaining'],
        'Calories': [total_intake, daily_target, max(0, remaining)]
    })
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        x='Category',
        y='Calories',
        color='Category'
    )
    st.altair_chart(chart, use_container_width=True)

# --- TAB 4: FITNESS CALCULATOR ---
with tab4:
    st.subheader("Log Exercise")
    
    ex_type = st.selectbox("Exercise Type", list(EXERCISE_DB.keys()))
    duration = st.number_input("Duration (minutes)", min_value=1, value=30)
    # Optional parameters (placeholder for logic)
    hr = st.text_input("Avg Heart Rate (Optional)")
    
    # Simple MET calculation: Calories = MET * Weight(kg) * Duration(hr)
    # Assuming standard weight of 70kg for demo if not set
    weight = st.number_input("Your Weight (kg)", value=70)
    
    met = EXERCISE_DB[ex_type]
    est_burn = met * weight * (duration / 60)
    
    st.write(f"Estimated Burn: **{est_burn:.0f} kcal**")
    
    manual_burn = st.number_input("Override Calories Burned", value=int(est_burn))
    
    if st.button("Log Exercise"):
        st.session_state.log.append({
            'type': 'Exercise',
            'name': ex_type,
            'amount': f"{duration} mins",
            'calories': manual_burn, # Note: Burn is stored as positive but subtracted in calculation
            'date': datetime.date.today()
        })
        st.success("Exercise Logged!")