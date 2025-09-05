import streamlit as st
import os
import sys
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Import backend components
from backend.agents.flow import medical_flow
from backend.utils.config import config
from backend.database.patient_db import patient_db
from backend.database.appointment_db import appointment_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def initialize_app():
    """Initialize the Streamlit app"""
    st.set_page_config(
        page_title="Medical AI Scheduling Agent",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Validate configuration
    if not config.validate_config():
        st.error("⚠️ Missing required environment variables. Please check your .env file.")
        st.stop()

def display_header():
    """Display app header"""
    st.title("🏥 Medical AI Scheduling Agent")
    st.markdown("""
    **Welcome to our AI-powered appointment scheduling system!**
    
    I can help you:
    - Schedule new appointments
    - Lookup existing patients
    - Find available slots
    - Handle insurance information
    - Send automated reminders
    """)

def display_sidebar():
    """Display sidebar with system information"""
    with st.sidebar:
        st.header("🔧 System Status")
        
        # Configuration status
        if config.validate_config():
            st.success("✅ Configuration Valid")
        else:
            st.error("❌ Configuration Issues")
        
        st.header("👨‍⚕️ Available Doctors")
        for doctor in config.DOCTORS:
            st.write(f"• {doctor}")
        
        st.header("⏰ Clinic Hours")
        st.write(f"• {config.CLINIC_START_HOUR}:00 AM - {config.CLINIC_END_HOUR}:00 PM")
        st.write("• Monday - Friday")
        
        st.header("📋 Features")
        features = [
            "Patient Greeting",
            "Patient Lookup", 
            "Smart Scheduling",
            "Calendar Integration",
            "Insurance Collection",
            "Appointment Confirmation",
            "Form Distribution",
            "Reminder System"
        ]
        for feature in features:
            st.write(f"✅ {feature}")

def display_chat_interface():
    """Display the main chat interface"""
    
    # Initialize session state
    if "messages" not in st.session_state:
        st.session_state.messages = []
        st.session_state.conversation_complete = False
    
    # Display chat history
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
    
    # Chat input
    if not st.session_state.conversation_complete:
        if prompt := st.chat_input("Type your message here... (e.g., 'Hi, I'm John Doe, DOB 1990-01-15, want to see Dr Asha Rao tomorrow morning')"):
            
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            with st.chat_message("user"):
                st.write(prompt)
            
            # Process message through the AI workflow
            with st.chat_message("assistant"):
                with st.spinner("Processing your request..."):
                    
                    # Use the LangGraph flow
                    result = medical_flow.process_message(
                        user_input=prompt,
                        conversation_history=st.session_state.messages[:-1]  # Exclude the current message
                    )
                    
                    if result["success"]:
                        # Extract assistant messages from result
                        new_messages = result["messages"]
                        assistant_messages = [msg for msg in new_messages if msg["role"] == "assistant"]
                        
                        if assistant_messages:
                            # Display the latest assistant message
                            latest_response = assistant_messages[-1]["content"]
                            st.write(latest_response)
                            
                            # Add to session state
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": latest_response
                            })
                        
                        # Check if conversation is complete
                        if result["is_complete"]:
                            st.session_state.conversation_complete = True
                            st.success("🎉 Appointment booking completed!")
                            
                            # Display appointment summary
                            if result["appointment"]:
                                display_appointment_summary(result["appointment"], result["patient"])
                        
                        # Handle followup questions
                        elif result["needs_followup"] and result["followup_question"]:
                            st.info("ℹ️ Additional information needed")
                    
                    else:
                        # Display errors
                        error_msg = "I'm sorry, there was an error processing your request:\n\n"
                        error_msg += "\n".join([f"• {error}" for error in result["errors"]])
                        st.error(error_msg)
                        
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": error_msg
                        })
    
    else:
        st.info("✅ Appointment booking completed! Start a new conversation to book another appointment.")
        if st.button("Start New Conversation"):
            st.session_state.messages = []
            st.session_state.conversation_complete = False
            st.experimental_rerun()

def display_appointment_summary(appointment, patient):
    """Display appointment summary"""
    st.markdown("---")
    st.subheader("📋 Appointment Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Patient Information:**")
        st.write(f"• Name: {patient.full_name}")
        st.write(f"• DOB: {patient.dob}")
        st.write(f"• Email: {patient.email or 'Not provided'}")
        st.write(f"• Phone: {patient.phone or 'Not provided'}")
        st.write(f"• Insurance: {patient.insurance_company or 'Not provided'}")
    
    with col2:
        st.markdown("**Appointment Details:**")
        st.write(f"• ID: {appointment.appointment_id}")
        st.write(f"• Doctor: {appointment.doctor}")
        
        # Format time
        apt_time = datetime.fromisoformat(appointment.start_time.replace('Z', '+00:00'))
        formatted_time = apt_time.strftime("%B %d, %Y at %I:%M %p")
        st.write(f"• Date & Time: {formatted_time}")
        st.write(f"• Duration: {appointment.duration_minutes} minutes")
        st.write(f"• Status: {appointment.status.title()}")

def display_admin_panel():
    """Display admin panel"""
    st.header("👩‍💼 Admin Panel")
    
    tab1, tab2, tab3 = st.tabs(["Recent Appointments", "Patient Database", "System Stats"])
    
    with tab1:
        st.subheader("Recent Appointments")
        try:
            appointments = appointment_db.get_all_appointments(days_ahead=30)
            
            if appointments:
                for apt in appointments[:10]:  # Show last 10
                    patient = patient_db.get_patient_by_id(apt.patient_id)
                    if patient:
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.write(f"**{patient.full_name}**")
                        with col2:
                            apt_time = datetime.fromisoformat(apt.start_time.replace('Z', '+00:00'))
                            st.write(apt_time.strftime("%m/%d %I:%M %p"))
                        with col3:
                            st.write(apt.doctor)
                        with col4:
                            status_color = {"scheduled": "🟡", "confirmed": "🟢", "cancelled": "🔴", "completed": "✅"}
                            st.write(f"{status_color.get(apt.status, '⚪')} {apt.status.title()}")
            else:
                st.info("No appointments found.")
                
        except Exception as e:
            st.error(f"Error loading appointments: {e}")
    
    with tab2:
        st.subheader("Patient Database")
        try:
            patients = patient_db.get_all_patients()
            
            if patients:
                for patient in patients[:20]:  # Show last 20
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.write(f"**{patient.full_name}**")
                    with col2:
                        st.write(patient.dob)
                    with col3:
                        st.write("📧" if patient.email else "❌")
                        st.write("📱" if patient.phone else "❌")
                    with col4:
                        st.write("🔄 Returning" if patient.is_returning else "🆕 New")
            else:
                st.info("No patients found.")
                
        except Exception as e:
            st.error(f"Error loading patients: {e}")
    
    with tab3:
        st.subheader("System Statistics")
        
        try:
            # Basic stats
            total_patients = len(patient_db.get_all_patients())
            total_appointments = len(appointment_db.get_all_appointments(days_ahead=30))
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Patients", total_patients)
            with col2:
                st.metric("Total Appointments", total_appointments)
            with col3:
                st.metric("Available Doctors", len(config.DOCTORS))
            with col4:
                st.metric("System Status", "🟢 Online")
                
        except Exception as e:
            st.error(f"Error loading stats: {e}")

def main():
    """Main application function"""
    
    # Initialize app
    initialize_app()
    
    # Create main layout
    display_header()
    display_sidebar()
    
    # Main content area
    main_tab, admin_tab = st.tabs(["💬 Chat Interface", "👩‍💼 Admin Panel"])
    
    with main_tab:
        display_chat_interface()
    
    with admin_tab:
        display_admin_panel()

if __name__ == "__main__":
    main()