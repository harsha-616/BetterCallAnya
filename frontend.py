import streamlit as st
import requests
import uuid
import json
import re
from datetime import datetime
import os
import time


API_URL = os.getenv("API_URL", "http://localhost:8080")

st.set_page_config(
    page_title="HealthVerse AI",
    page_icon="🏥",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .doctor-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #ddd;
        margin: 0.5rem 0;
    }
    .success-msg {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    .error-msg {
        background: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #f5c6cb;
    }
    .emergency-alert {
        background: #dc3545;
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        border: 3px solid #ff0000;
        margin: 1rem 0;
        text-align: center;
        font-weight: bold;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(220, 53, 69, 0); }
        100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
    }
    .emergency-button {
        background: #dc3545;
        color: white;
        border: none;
        padding: 1rem 2rem;
        border-radius: 8px;
        font-size: 1.2rem;
        font-weight: bold;
        cursor: pointer;
        margin: 0.5rem;
    }
    .emergency-info {
        background: #fff3cd;
        color: #856404;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #ffeaa7;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant",
         "content": "Hello! I'm your AI medical receptionist. Please describe your symptoms and I'll help you find the right specialist. In case of emergency, I can also contact emergency services for you."}
    ]
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "context" not in st.session_state:
    st.session_state.context = {}
if "waiting_for_phone" not in st.session_state:
    st.session_state.waiting_for_phone = False
if "booking_details" not in st.session_state:
    st.session_state.booking_details = None
if "backend_status" not in st.session_state:
    st.session_state.backend_status = "unknown"
if "emergency_mode" not in st.session_state:
    st.session_state.emergency_mode = False


def check_backend_connection():
    """Check if backend is running"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=3)
        if response.status_code == 200:
            st.session_state.backend_status = "connected"
            return True
    except:
        pass

    st.session_state.backend_status = "disconnected"
    return False


def is_valid_phone(phone: str) -> bool:
    """Validate Indian phone number"""
    return re.match(r'^[6-9]\d{9}$', phone.strip()) is not None


def make_api_request(endpoint, data, method="POST"):
    """Make API request with error handling"""
    try:
        if method == "POST":
            response = requests.post(f"{API_URL}{endpoint}", json=data, timeout=30)
        else:
            response = requests.get(f"{API_URL}{endpoint}", timeout=30)

        return response
    except requests.exceptions.Timeout:
        st.error("Request timed out. Please try again.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend. Please ensure the API server is running.")
        return None
    except Exception as e:
        st.error(f"Network error: {e}")
        return None


def handle_emergency_response(response_data):
    """Handle emergency detection response"""
    st.session_state.emergency_mode = True
    # Add emergency message to chat
    emergency_msg = response_data.get("response_text", "Emergency detected!")
    st.session_state.messages.append({"role": "assistant", "content": emergency_msg})
    

def handle_user_input(user_input: str):
    """Process user input"""
    st.session_state.messages.append({"role": "user", "content": user_input})

    # If waiting for phone number
    if st.session_state.waiting_for_phone:
        phone = user_input.strip()
        if is_valid_phone(phone):
            # Complete booking
            booking_data = st.session_state.booking_details.copy()
            booking_data["patient_phone"] = f"+91{phone}"

            with st.spinner("Booking appointment..."):
                response = make_api_request("/book", booking_data)

                if response and response.status_code == 201:
                    result = response.json()
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"✅ {result['message']}\n\n🏥 Hospital: {result['hospital_name']}"
                    })

                    # Store hospital info for directions
                    st.session_state.hospital_info = {
                        "name": result["hospital_name"],
                        "lat": result["latitude"],
                        "lon": result["longitude"]
                    }

                    # Reset booking state
                    st.session_state.waiting_for_phone = False
                    st.session_state.booking_details = None

                elif response:
                    error_msg = response.json().get("error", "Booking failed")
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"❌ {error_msg}"
                    })
                    st.session_state.waiting_for_phone = False

        else:
            st.session_state.messages.append({
                "role": "assistant",
                "content": "Please enter a valid 10-digit mobile number starting with 6, 7, 8, or 9."
            })

    # Regular chat flow with emergency detection
    else:
        with st.spinner("Analyzing..."):
            response = make_api_request("/chat", {
                "message": user_input,
                "session_id": st.session_state.session_id
            })

            if response and response.status_code == 200:
                data = response.json()

                # Check if emergency was detected
                if data.get("emergency_detected"):
                    handle_emergency_response(data)
                    return

                # Add bot response
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": data.get("response_text", "No response received")
                })

                # Update context
                st.session_state.context = data

            elif response:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", f"Server error: {response.status_code}")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"❌ {error_msg}"
                })


def manual_emergency_trigger():
    """Allow manual emergency call trigger"""
    if st.button("🚨 EMERGENCY - Call Now", key="manual_emergency", type="primary"):
        with st.spinner("Contacting emergency services..."):
            response = make_api_request("/trigger-emergency-call", {
                "message": "Manual emergency request from HealthVerse AI user"
            })

            if response and response.status_code == 200:
                st.success("Emergency call initiated! Help is on the way.")
                st.balloons()
            else:
                st.error("Failed to contact emergency services. Please call 108 directly.")


# Header
st.title("🏥 HealthVerse AI Receptionist")

# Connection status and emergency button
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    if check_backend_connection():
        st.success("Backend Online")
    else:
        st.error("Backend Offline")
        st.stop()

with col2:
    manual_emergency_trigger()


# Emergency mode banner
if st.session_state.emergency_mode:
    st.markdown("""
    <div class="emergency-alert">
        🚨 EMERGENCY MODE ACTIVE 🚨<br>
        Please follow emergency protocols immediately
    </div>
    """, unsafe_allow_html=True)

# Main chat area
st.subheader("💬 Conversation")

# Display messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Show doctors if available (only in non-emergency mode)
if (not st.session_state.emergency_mode and
        st.session_state.context.get("doctors") and
        st.session_state.context.get("next_action") == "book_appointment"):

    st.markdown("---")
    st.subheader("👩‍⚕️ Available Doctors")

    doctors = st.session_state.context["doctors"]

    for i, doctor in enumerate(doctors):
        with st.expander(f"Dr. {doctor['name']} - Rating: {doctor['rating']:.1f}⭐", expanded=True):
            st.write(f"**Hospital:** {doctor['hospital']}")

            if doctor.get('slots'):
                st.write("**Available Slots Today:**")

                # Create columns for slots
                cols = st.columns(min(3, len(doctor['slots'])))
                for j, slot in enumerate(doctor['slots'][:6]):
                    col_idx = j % len(cols)
                    with cols[col_idx]:
                        if st.button(
                                f"📅 {slot}",
                                key=f"book_{i}_{j}",
                                use_container_width=True
                        ):
                            # Prepare booking
                            slot_datetime = datetime.now().replace(
                                hour=int(slot.split(':')[0]) % 12 + (12 if 'PM' in slot else 0),
                                minute=int(slot.split(':')[1].split()[0]),
                                second=0,
                                microsecond=0
                            )

                            st.session_state.booking_details = {
                                "doctor_id": doctor["id"],
                                "slot": slot_datetime.isoformat(),
                                "reason": ", ".join(st.session_state.context.get("symptoms", [])),
                                "disease": st.session_state.context.get("predicted_condition", "Unknown")
                            }

                            st.session_state.waiting_for_phone = True

                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"Great! You've selected Dr. {doctor['name']} at {slot}.\n\nPlease provide your 10-digit mobile number to confirm the booking."
                            })

                            st.rerun()
            else:
                st.write("❌ No slots available today")

# Show directions if hospital info is available (only in non-emergency mode)
if not st.session_state.emergency_mode and "hospital_info" in st.session_state:
    st.markdown("---")
    st.subheader("🗺️ Hospital Directions")

    col1, col2 = st.columns(2)
    with col1:
        st.info(f"📍 **{st.session_state.hospital_info['name']}**\n\nYour appointment is confirmed!")

    with col2:
        if st.button("🧭 Get Directions", type="primary"):
            # Create Google Maps URL
            hospital_lat = st.session_state.hospital_info['lat']
            hospital_lon = st.session_state.hospital_info['lon']
            maps_url = f"https://www.google.com/maps/dir/?api=1&destination={hospital_lat},{hospital_lon}"

            st.markdown(f"[🗺️ Open in Google Maps]({maps_url})")
            st.balloons()

# Emergency information panel
if st.session_state.emergency_mode:
    st.markdown("---")
    st.subheader("🚨 Emergency Information")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Emergency Numbers:**
        - 🚑 Ambulance: 108
        - 🚓 Police: 100
        - 🔥 Fire: 101
        - 📞 Women Helpline: 1091
        """)

    with col2:
        st.markdown("""
        **What to do now:**
        1. Call 108 immediately
        2. Stay calm and don't panic
        3. Follow dispatcher instructions
        4. Have someone stay with you
        5. Prepare medical history if possible
        """)

    if st.button("✅ Emergency Resolved", type="secondary"):
        st.session_state.emergency_mode = False
        st.session_state.messages.append({
            "role": "assistant",
            "content": "Emergency mode cleared. How else can I help you today?"
        })
        st.rerun()

# Chat input (disabled during emergency mode for critical symptoms)
chat_placeholder = "⚠️ Emergency mode active - call 108 now" if st.session_state.emergency_mode else "Describe your symptoms or book an appointment..."

if prompt := st.chat_input(chat_placeholder, disabled=st.session_state.emergency_mode):
    handle_user_input(prompt)
    st.rerun()

# Sidebar with debug info and emergency controls
with st.sidebar:
    st.header("🔧 System Status")

    if st.session_state.backend_status == "connected":
        st.success("✅ Backend Connected")
    else:
        st.error("❌ Backend Disconnected")

    st.write(f"**API URL:** {API_URL}")
    st.write(f"**Session:** {st.session_state.session_id[:8]}...")

    # Emergency status
    if st.session_state.emergency_mode:
        st.error("🚨 EMERGENCY MODE")
    else:
        st.success("😊 Normal Mode")

    if st.session_state.context.get("symptoms"):
        st.write("**Current Symptoms:**")
        for symptom in st.session_state.context["symptoms"]:
            st.write(f"• {symptom}")

    if st.session_state.context.get("predicted_condition"):
        st.write(f"**Condition:** {st.session_state.context['predicted_condition']}")

    # Emergency testing (admin use)
    st.markdown("---")
    st.subheader("🔧 Emergency Testing")

    if st.button("Test Emergency Detection"):
        test_input = "I'm having severe chest pain and can't breathe"
        response = make_api_request("/emergency-check", {"message": test_input})
        if response and response.status_code == 200:
            result = response.json()
            if result["is_emergency"]:
                st.error(f"Emergency detected: {result['trigger']}")
            else:
                st.success("No emergency detected")

    if st.button("📄 Reset Session"):
        # Clear all session state
        keys_to_keep = []  # Keep nothing, full reset
        for key in list(st.session_state.keys()):
            if key not in keys_to_keep:
                del st.session_state[key]
        st.rerun()

# Footer
st.markdown("---")
st.caption("HealthVerse AI Receptionist - Your intelligent healthcare companion with emergency detection")