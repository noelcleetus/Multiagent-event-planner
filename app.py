import streamlit as st
import pandas as pd
from groq import Groq
import re

# =============================
# CONFIG & API SETUP
# =============================
st.set_page_config(page_title="Pro Event Planner AI", layout="wide")

if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    api_key = "xxx" 

client = Groq(api_key=api_key)

# =============================
# AGENT CLASS
# =============================
class Agent:
    def __init__(self, role):
        self.role = role

    def run(self, prompt):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": self.role},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error contacting AI: {str(e)}"

# =============================
# HELPERS
# =============================
def extract_markdown_table(text):
    lines = text.split("\n")
    table_lines = [line for line in lines if line.strip().startswith("|")]
    return "\n".join(table_lines)

def markdown_to_df(md_table):
    try:
        lines = [line.strip() for line in md_table.split("\n") if line.strip() and "---" not in line]
        if not lines: return pd.DataFrame()
        rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
        
        # Build DataFrame
        df = pd.DataFrame(rows[1:], columns=rows[0])
        
        # FINAL KILLER FIX: Remove rows that repeat the header labels
        if not df.empty:
            df = df[~df.iloc[:, 0].str.contains("Resource|Original Cost|Optimized", case=False, na=False)]
        return df
    except:
        return pd.DataFrame()

def clean_currency(val):
    if isinstance(val, (int, float)): return float(val)
    if not val: return 0.0
    cleaned = str(val).upper().replace('AED', '').replace(',', '').strip()
    try:
        if '-' in cleaned:
            cleaned = cleaned.split('-')[0].strip()
        return float(cleaned)
    except:
        return 0.0

def display_color_swatches(text):
    hex_codes = re.findall(r'#(?:[0-9a-fA-F]{3}){1,2}', text)
    if hex_codes:
        unique_hex = list(dict.fromkeys(hex_codes))
        st.write("### 🎨 Extracted Color Palette")
        cols = st.columns(len(unique_hex))
        for i, code in enumerate(unique_hex):
            with cols[i]:
                st.color_picker(label=code, value=code, key=f"swatch_{code}_{i}", disabled=True)

# =============================
# AGENT INSTANCES
# =============================
event_planner = Agent("You are a professional world-class event planner. You specialize in high-end aesthetics and detailed logistics.")
vendor_agent = Agent("You estimate realistic market prices for event resources in AED.")
budget_agent = Agent("You are a strategic financial optimizer. Your goal is to keep costs near the limit without sacrificing the essential vibe.")
designer_agent = Agent("You are a creative director. You suggest elegant color palettes (with Hex codes) and visual themes.")

# =============================
# UI & INPUT FORM
# =============================
st.title("✨ Pro Multi-Agent Event Planner")

with st.sidebar:
    st.header("📋 Event Specifications")
    with st.form("event_details"):
        event_name = st.text_input("Event Name", "My Luxury Event")
        event_type_selection = st.selectbox("Category", ["Wedding", "Gala", "Party", "Workshop", "Conference", "Other..."])
        custom_type = st.text_input("If 'Other', specify:", "")
        final_event_type = custom_type if event_type_selection == "Other..." else event_type_selection

        event_description = st.text_area("Event Vision", placeholder="Describe the dream...")
        vibe_tags = st.multiselect("Vibe", ["Modern", "Luxury", "Minimalist", "Traditional", "Bohemian", "Tech-forward"], default=["Modern"])
        
        attendees = st.number_input("Attendees", min_value=1, value=100)
        max_budget = st.number_input("Budget Limit (AED)", min_value=1, value=50000)
        extra_notes = st.text_area("Specific Requirements", "Premium catering, floral decor.")
        
        submit_btn = st.form_submit_button("🚀 Generate Full Plan")

# =============================
# SESSION STATE & LOGIC
# =============================
if "data" not in st.session_state:
    st.session_state.data = {"plan": None, "costs": None, "opt": None, "mood": None, "meta": {}}

if submit_btn:
    vibe_str = ", ".join(vibe_tags)
    with st.spinner("🤖 Agents are collaborating..."):
        st.session_state.data["meta"] = {"name": event_name, "limit": max_budget}
        
        # 1. Plan
        plan_prompt = f"Plan a {final_event_type} named '{event_name}' for {attendees} attendees. Vibe: {vibe_str}. Vision: {event_description}. Provide Venue, Schedule, and Resource List."
        st.session_state.data["plan"] = event_planner.run(plan_prompt)

        # 2. Mood
        mood_prompt = f"For event '{event_name}' ({vibe_str}), suggest a color palette with Hex codes and a 3-sentence theme description."
        st.session_state.data["mood"] = designer_agent.run(mood_prompt)

        # 3. Costs
        vendor_prompt = f"Based on this plan:\n{st.session_state.data['plan']}\nCreate a MARKDOWN COST TABLE: | Resource | Quantity | Cost per Unit (AED) | Total Cost (AED) |"
        cost_out = vendor_agent.run(vendor_prompt)
        st.session_state.data["costs"] = markdown_to_df(extract_markdown_table(cost_out))

        # 4. Optimization
        cost_str = st.session_state.data["costs"].to_string()
        budget_prompt = f"STRICT LIMIT: {max_budget} AED. Optimize this list. A slight 5% overage is okay for quality. Create a MARKDOWN TABLE: | Resource | Original Cost (AED) | Optimized Cost (AED) | Savings (AED) | \n{cost_str}"
        opt_out = budget_agent.run(budget_prompt)
        st.session_state.data["opt"] = markdown_to_df(extract_markdown_table(opt_out))

# =============================
# DISPLAY
# =============================
if st.session_state.data["plan"]:
    tab1, tab2, tab3, tab4 = st.tabs(["📌 Plan", "🎨 Mood Board", "💰 Estimates", "📉 Interactive Budget"])
    
    with tab1: st.markdown(st.session_state.data["plan"])
    with tab2:
        st.info(st.session_state.data["mood"])
        display_color_swatches(st.session_state.data["mood"])
    with tab3: st.dataframe(st.session_state.data["costs"], use_container_width=True)
    with tab4:
        edited_df = st.data_editor(st.session_state.data["opt"], use_container_width=True, key="budget_editor")
        edited_df = edited_df[~edited_df.iloc[:, 0].str.contains("Resource", case=False, na=False)]

        try:
            orig_t = edited_df.iloc[:, 1].apply(clean_currency).sum()
            opt_t = edited_df.iloc[:, 2].apply(clean_currency).sum()
            st.columns(3)[0].metric("Original", f"AED {orig_t:,.0f}")
            st.columns(3)[1].metric("Final", f"AED {opt_t:,.0f}", delta=f"{max_budget-opt_t:,.0f}")
            st.columns(3)[2].metric("Savings", f"AED {orig_t-opt_t:,.0f}")
        except: st.warning("Check data format.")

    st.download_button("📥 Download Budget", edited_df.to_csv(index=False).encode('utf-8'), "budget.csv")
