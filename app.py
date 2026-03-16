import streamlit as st
import pandas as pd
from groq import Groq

# =============================
# CONFIG & API SETUP
# =============================
st.set_page_config(page_title="Pro Event Planner AI", layout="wide")

# Check if we are on Streamlit Cloud (Secrets) or local
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    # This falls back to 'xxx' so the code doesn't crash if the key is missing
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
        return pd.DataFrame(rows[1:], columns=rows[0])
    except:
        return pd.DataFrame()

def clean_currency(val):
    if isinstance(val, (int, float)): return float(val)
    if not val: return 0.0
    cleaned = str(val).upper().replace('AED', '').replace(',', '').strip()
    try:
        return float(cleaned)
    except:
        return 0.0

# =============================
# AGENT INSTANCES
# =============================
event_planner = Agent("You are a professional world-class event planner. You specialize in high-end aesthetics and detailed logistics.")
vendor_agent = Agent("You estimate realistic market prices for event resources in AED.")
budget_agent = Agent("You optimize budgets to stay under a specific limit while maintaining high quality.")
designer_agent = Agent("You are a creative director. You suggest elegant color palettes (with Hex codes) and visual themes for events.")

# =============================
# UI & INPUT FORM
# =============================
st.title("✨ Pro Multi-Agent Event Planner")

with st.sidebar:
    st.header("📋 Event Specifications")
    with st.form("event_details"):
        event_name = st.text_input("Event Name", " Enter Event Name”)
        
        event_type_selection = st.selectbox(
            "Event Category", 
            ["Wedding", "Celebration", "Gala", "Party", "Workshop", "Conference", "Other..."]
        )
        
        custom_type = st.text_input("If 'Other', specify type here:", "")
        final_event_type = custom_type if event_type_selection == "Other..." else event_type_selection

        attendees = st.number_input("Expected Attendees", min_value=1, value=100)
        max_budget = st.number_input("Budget Limit (AED)", min_value=1, value=50000)
        extra_notes = st.text_area("Specific Requirements", "Elegant decor, premium catering, and photography.")
        
        submit_btn = st.form_submit_button("🚀 Generate Full Plan & Mood Board")

# =============================
# SESSION STATE
# =============================
if "data" not in st.session_state:
    st.session_state.data = {"plan": None, "costs": None, "opt": None, "mood": None, "meta": {}}

# =============================
# EXECUTION LOGIC
# =============================
if submit_btn:
    actual_type = final_event_type if final_event_type else event_type_selection
    
    with st.spinner(f"🤖 Agents are collaborating on your {actual_type}..."):
        st.session_state.data["meta"] = {"name": event_name, "limit": max_budget}
        
        # 1. Logic: General Plan
        plan_prompt = (
            f"Plan a {actual_type} named '{event_name}' for {attendees} attendees. "
            f"Requirements: {extra_notes}. Provide Venue concept, Schedule, and Resource List."
        )
        st.session_state.data["plan"] = event_planner.run(plan_prompt)

        # 2. Logic: Mood Board & Theme
        mood_prompt = f"Based on the event '{event_name}' ({actual_type}), suggest a sophisticated color palette with Hex codes and a 3-sentence visual theme description."
        st.session_state.data["mood"] = designer_agent.run(mood_prompt)

        # 3. Logic: Costs
        vendor_prompt = f"Based on this plan:\n{st.session_state.data['plan']}\nCreate a MARKDOWN COST TABLE. Columns: | Resource | Quantity | Cost per Unit (AED) | Total Cost (AED) |"
        cost_out = vendor_agent.run(vendor_prompt)
        st.session_state.data["costs"] = markdown_to_df(extract_markdown_table(cost_out))

        # 4. Logic: Optimization
        cost_str = st.session_state.data["costs"].to_string()
        budget_prompt = f"Limit: {max_budget} AED. Optimize this list:\n{cost_str}\nCreate a MARKDOWN TABLE: | Resource | Original Cost (AED) | Optimized Cost (AED) | Savings (AED) |"
        opt_out = budget_agent.run(budget_prompt)
        st.session_state.data["opt"] = markdown_to_df(extract_markdown_table(opt_out))

# =============================
# DISPLAY RESULTS
# =============================
if st.session_state.data["plan"]:
    st.success(f"Successfully planned {st.session_state.data['meta']['name']}!")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📌 Detailed Plan", "🎨 Mood Board", "💰 Estimates", "📉 Interactive Budget"])
    
    with tab1:
        st.markdown(st.session_state.data["plan"])
    
    with tab2:
        st.subheader("🎨 Visual Direction")
        st.info(st.session_state.data["mood"])
    
    with tab3:
        st.dataframe(st.session_state.data["costs"], use_container_width=True)
    
    with tab4:
        st.info("💡 **Edit Prices:** Modify 'Optimized Cost' below to update totals.")
        edited_df = st.data_editor(st.session_state.data["opt"], use_container_width=True, key="budget_editor")
        
        try:
            orig_total = edited_df.iloc[:, 1].apply(clean_currency).sum()
            opt_total = edited_df.iloc[:, 2].apply(clean_currency).sum()
            actual_savings = orig_total - opt_total
            budget_limit = st.session_state.data["meta"]["limit"]

            m1, m2, m3 = st.columns(3)
            m1.metric("Original Total", f"AED {orig_total:,.2f}")
            m2.metric("Final Total", f"AED {opt_total:,.2f}", 
                      delta=f"{budget_limit - opt_total:,.2f} vs Limit", 
                      delta_color="normal" if opt_total <= budget_limit else "inverse")
            m3.metric("Total Savings", f"AED {actual_savings:,.2f}")

            if opt_total > budget_limit:
                st.error(f"⚠️ Over budget by AED {opt_total - budget_limit:,.2f}")
        except:
            st.warning("Ensure price columns contain numbers.")

    st.divider()
    st.download_button("📥 Download Budget CSV", edited_df.to_csv(index=False).encode('utf-8'), f"{st.session_state.data['meta']['name']}.csv", "text/csv")
else:
    st.write("👈 Set your specifications and click 'Generate' to begin.")
