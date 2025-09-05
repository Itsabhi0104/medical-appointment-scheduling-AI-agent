from typing import Dict, Any, List, Optional
from langgraph.graph import Graph, StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
import logging
from .nlu_agent import nlu_agent
from .scheduling_agent import scheduling_agent
from .reminder_agent import reminder_agent

logger = logging.getLogger(__name__)

class ConversationState(TypedDict):
    messages: List[Dict[str, str]]
    current_step: str
    patient_data: Dict[str, Any]
    appointment_data: Dict[str, Any]
    patient_object: Optional[Any]
    appointment_object: Optional[Any]
    available_slots: List[Dict[str, Any]]
    errors: List[str]
    needs_followup: bool
    followup_question: str
    is_complete: bool

class MedicalSchedulingFlow:
    def __init__(self):
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        
        workflow = StateGraph(ConversationState)
        
        # Add nodes
        workflow.add_node("parse_input", self._parse_input)
        workflow.add_node("lookup_patient", self._lookup_patient)
        workflow.add_node("collect_missing_info", self._collect_missing_info)
        workflow.add_node("find_slots", self._find_slots)
        workflow.add_node("create_appointment", self._create_appointment)
        workflow.add_node("setup_reminders", self._setup_reminders)
        workflow.add_node("complete_booking", self._complete_booking)
        
        # Set entry point
        workflow.set_entry_point("parse_input")
        
        # Add edges with conditions
        workflow.add_conditional_edges(
            "parse_input",
            self._should_collect_more_info,
            {
                "collect_info": "collect_missing_info",
                "lookup_patient": "lookup_patient"
            }
        )
        
        workflow.add_conditional_edges(
            "collect_missing_info",
            self._should_collect_more_info,
            {
                "collect_info": "collect_missing_info",
                "lookup_patient": "lookup_patient"
            }
        )
        
        workflow.add_edge("lookup_patient", "find_slots")
        workflow.add_edge("find_slots", "create_appointment")
        workflow.add_edge("create_appointment", "setup_reminders")
        workflow.add_edge("setup_reminders", "complete_booking")
        workflow.add_edge("complete_booking", END)
        
        return workflow.compile()
    
    def _parse_input(self, state: ConversationState) -> ConversationState:
        """Parse user input using NLU agent"""
        try:
            # Get the latest message
            if not state["messages"]:
                return state
            
            latest_message = state["messages"][-1]["content"]
            
            # Parse with NLU agent
            parsed_result = nlu_agent.parse_utterance(latest_message, use_llm=True)
            
            # Update state with parsed data
            new_patient_data = {}
            new_appointment_data = {}
            
            if parsed_result.first_name:
                new_patient_data["first_name"] = parsed_result.first_name
            if parsed_result.last_name:
                new_patient_data["last_name"] = parsed_result.last_name
            if parsed_result.dob:
                new_patient_data["dob"] = parsed_result.dob
            if parsed_result.email:
                new_patient_data["email"] = parsed_result.email
            if parsed_result.phone:
                new_patient_data["phone"] = parsed_result.phone
            if parsed_result.insurance:
                new_patient_data["insurance"] = parsed_result.insurance
            if parsed_result.member_id:
                new_patient_data["member_id"] = parsed_result.member_id
            
            if parsed_result.doctor:
                new_appointment_data["doctor"] = parsed_result.doctor
            if parsed_result.preferred_date:
                new_appointment_data["preferred_date"] = parsed_result.preferred_date
            if parsed_result.preferred_time_window:
                new_appointment_data["preferred_time_window"] = parsed_result.preferred_time_window
            if parsed_result.reason:
                new_appointment_data["reason"] = parsed_result.reason
            
            # Merge with existing data
            state["patient_data"].update(new_patient_data)
            state["appointment_data"].update(new_appointment_data)
            state["needs_followup"] = parsed_result.needs_followup
            state["followup_question"] = parsed_result.followup_question or ""
            state["current_step"] = "parsed"
            
            logger.info(f"Parsed input - Patient data: {state['patient_data']}")
            logger.info(f"Parsed input - Appointment data: {state['appointment_data']}")
            
        except Exception as e:
            logger.error(f"Error parsing input: {e}")
            state["errors"].append(f"Error parsing input: {str(e)}")
        
        return state
    
    def _lookup_patient(self, state: ConversationState) -> ConversationState:
        """Lookup or create patient"""
        try:
            patient, is_new, errors = scheduling_agent.lookup_or_create_patient(state["patient_data"])
            
            if errors:
                state["errors"].extend(errors)
                return state
            
            if patient:
                state["patient_object"] = patient
                state["current_step"] = "patient_found"
                
                # Set appointment duration based on patient type
                if is_new:
                    state["appointment_data"]["duration_minutes"] = 60
                    state["appointment_data"]["patient_type"] = "new"
                else:
                    state["appointment_data"]["duration_minutes"] = 30
                    state["appointment_data"]["patient_type"] = "returning"
                
                logger.info(f"Patient lookup successful: {patient.patient_id} ({'new' if is_new else 'returning'})")
            else:
                state["errors"].append("Failed to create patient record")
                
        except Exception as e:
            logger.error(f"Error in patient lookup: {e}")
            state["errors"].append(f"Error in patient lookup: {str(e)}")
        
        return state
    
    def _collect_missing_info(self, state: ConversationState) -> ConversationState:
        """Collect missing information from user"""
        state["current_step"] = "collecting_info"
        
        # The followup question is already set by NLU agent
        if state["followup_question"]:
            # Add the followup question as a system message
            state["messages"].append({
                "role": "assistant",
                "content": state["followup_question"]
            })
        
        return state
    
    def _find_slots(self, state: ConversationState) -> ConversationState:
        """Find available appointment slots"""
        try:
            if not state["patient_object"]:
                state["errors"].append("Patient not found")
                return state
            
            doctor = state["appointment_data"].get("doctor")
            preferred_date = state["appointment_data"].get("preferred_date")
            duration = state["appointment_data"].get("duration_minutes", 30)
            time_window = state["appointment_data"].get("preferred_time_window")
            
            if not doctor or not preferred_date:
                state["errors"].append("Doctor and date are required")
                return state
            
            # Get suggested slots
            slots = scheduling_agent.get_suggested_slots(
                doctor, preferred_date, time_window, duration
            )
            
            state["available_slots"] = slots
            state["current_step"] = "slots_found"
            
            logger.info(f"Found {len(slots)} available slots")
            
        except Exception as e:
            logger.error(f"Error finding slots: {e}")
            state["errors"].append(f"Error finding slots: {str(e)}")
        
        return state
    
    def _create_appointment(self, state: ConversationState) -> ConversationState:
        """Create the appointment"""
        try:
            if not state["available_slots"]:
                state["errors"].append("No available slots found")
                return state
            
            # Use the first available slot (or user could select)
            selected_slot = state["available_slots"][0]
            
            # Update appointment data with selected slot
            state["appointment_data"]["start_time"] = selected_slot["start_time"]
            state["appointment_data"]["end_time"] = selected_slot["end_time"]
            
            # Create appointment
            appointment, errors = scheduling_agent.create_appointment(
                state["patient_object"], 
                state["appointment_data"]
            )
            
            if errors:
                state["errors"].extend(errors)
                return state
            
            if appointment:
                state["appointment_object"] = appointment
                state["current_step"] = "appointment_created"
                logger.info(f"Appointment created: {appointment.appointment_id}")
            else:
                state["errors"].append("Failed to create appointment")
                
        except Exception as e:
            logger.error(f"Error creating appointment: {e}")
            state["errors"].append(f"Error creating appointment: {str(e)}")
        
        return state
    
    def _setup_reminders(self, state: ConversationState) -> ConversationState:
        """Setup automated reminders"""
        try:
            if not state["appointment_object"]:
                state["errors"].append("No appointment to setup reminders for")
                return state
            
            # Create 3 automated reminders
            reminders = reminder_agent.create_appointment_reminders(
                state["appointment_object"].appointment_id
            )
            
            state["current_step"] = "reminders_setup"
            logger.info(f"Setup {len(reminders)} reminders for appointment")
            
        except Exception as e:
            logger.error(f"Error setting up reminders: {e}")
            state["errors"].append(f"Error setting up reminders: {str(e)}")
        
        return state
    
    def _complete_booking(self, state: ConversationState) -> ConversationState:
        """Complete the booking process"""
        state["current_step"] = "completed"
        state["is_complete"] = True
        
        # Generate confirmation message
        if state["appointment_object"] and state["patient_object"]:
            appointment = state["appointment_object"]
            patient = state["patient_object"]
            
            # Format appointment time
            from datetime import datetime
            apt_time = datetime.fromisoformat(appointment.start_time.replace('Z', '+00:00'))
            formatted_time = apt_time.strftime("%B %d, %Y at %I:%M %p")
            
            confirmation_msg = f"""
✅ Appointment Confirmed!

Patient: {patient.full_name}
Doctor: {appointment.doctor}
Date & Time: {formatted_time}
Duration: {appointment.duration_minutes} minutes
Appointment ID: {appointment.appointment_id}

📧 You will receive:
• Intake forms via email (for new patients)
• 3 automated reminders (24h, 4h, 1h before)
• Calendar invitation

Thank you for booking with us!
"""
            
            state["messages"].append({
                "role": "assistant",
                "content": confirmation_msg
            })
        
        return state
    
    def _should_collect_more_info(self, state: ConversationState) -> str:
        """Determine if more information needs to be collected"""
        if state["needs_followup"]:
            return "collect_info"
        
        # Check if we have minimum required info
        patient_data = state["patient_data"]
        appointment_data = state["appointment_data"]
        
        required_patient_fields = ["first_name", "last_name", "dob"]
        required_appointment_fields = ["doctor", "preferred_date"]
        
        missing_patient = [f for f in required_patient_fields if not patient_data.get(f)]
        missing_appointment = [f for f in required_appointment_fields if not appointment_data.get(f)]
        
        if missing_patient or missing_appointment:
            return "collect_info"
        
        return "lookup_patient"
    
    def process_message(self, user_input: str, conversation_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Process a user message through the workflow"""
        
        # Initialize state
        initial_state = ConversationState(
            messages=conversation_history or [],
            current_step="start",
            patient_data={},
            appointment_data={},
            patient_object=None,
            appointment_object=None,
            available_slots=[],
            errors=[],
            needs_followup=False,
            followup_question="",
            is_complete=False
        )
        
        # Add user message
        initial_state["messages"].append({
            "role": "user",
            "content": user_input
        })
        
        try:
            # Run the workflow
            final_state = self.graph.invoke(initial_state)
            
            # Return relevant information
            return {
                "success": len(final_state["errors"]) == 0,
                "errors": final_state["errors"],
                "messages": final_state["messages"],
                "current_step": final_state["current_step"],
                "is_complete": final_state["is_complete"],
                "patient": final_state["patient_object"],
                "appointment": final_state["appointment_object"],
                "available_slots": final_state["available_slots"],
                "needs_followup": final_state["needs_followup"],
                "followup_question": final_state["followup_question"]
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "success": False,
                "errors": [f"Error processing message: {str(e)}"],
                "messages": initial_state["messages"],
                "current_step": "error",
                "is_complete": False
            }

# Global instance
medical_flow = MedicalSchedulingFlow()