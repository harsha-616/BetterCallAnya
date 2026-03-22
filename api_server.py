import os
import re
import json
import uuid
import psycopg2
from google import genai
from google.genai import types
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime, timedelta
import warnings
from twilio.rest import Client

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning)

print("🚀 Starting HealthVerse AI Backend...")
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend communication

# --- Configuration & Setup ---
HISTORY_DIR = "chat_sessions"
os.makedirs(HISTORY_DIR, exist_ok=True)

# Configure Google Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY not found in environment. Check your .env file.")
    exit()

try:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    gemini_model = "gemini-2.5-flash"
    print("✅ Gemini configured successfully")
except Exception as e:
    print(f"❌ Failed to configure Gemini: {e}")
    exit()
# Configure Twilio for Emergency Calls
try:
    twilio_client = Client(
        os.getenv("TWILIO_ACCOUNT_SID", "YOUR TWILIO_ACCOUNT_SID"),
        os.getenv("TWILIO_AUTH_TOKEN", "YOUR TWILIO_AUTH_TOKEN")
    )
    TWILIO_NUMBER = os.getenv("TWILIO_NUMBER", "YOUR TWILIO_NUMBER")
    EMERGENCY_NUMBER = os.getenv("EMERGENCY_NUMBER", "YOUR EMERGENCY_NUMBER")
    print("✅ Twilio configured for emergency calls")
except Exception as e:
    print(f"⚠️ Twilio configuration warning: {e}")
    twilio_client = None


class EmergencyClassifier:
    """Emergency detection system using Gemini AI"""

    def __init__(self):
        self.model = gemini_model
        self.emergency_keywords = [
            "severe chest pain", "heart attack", "stroke", "can't breathe",
            "severe bleeding", "unconscious", "suicide", "overdose",
            "severe head injury", "anaphylaxis", "severe allergic reaction",
            "seizure", "convulsion", "choking", "poisoning", "thunderclap headache"
        ]

    def is_emergency(self, user_input: str) -> dict:
        """Classify if input represents a medical emergency"""
        user_input_normalized = user_input.lower().replace("chest ache", "chest pain")

        # Quick keyword check first
        for keyword in self.emergency_keywords:
            if keyword in user_input_normalized:
                return {
                    "is_emergency": True,
                    "confidence": 0.9,
                    "trigger": f"Emergency keyword detected: {keyword}",
                    "classification": "emergency"
                }

        # Use Gemini for sophisticated analysis
        prompt = f"""
        CRITICAL MEDICAL EMERGENCY DETECTION TASK:

        Analyze the following symptom description to determine if it represents a medical emergency requiring immediate intervention:

        EMERGENCY INDICATORS (Respond with "emergency"):
        - Severe chest pain, heart attack symptoms
        - Stroke symptoms (sudden confusion, speech problems, weakness)
        - Severe breathing difficulties, can't breathe
        - Severe bleeding or trauma
        - Loss of consciousness
        - Suicide ideation or attempt
        - Drug overdose or poisoning
        - Severe allergic reactions (anaphylaxis)
        - Severe burns or injuries
        - High fever with severe symptoms in children
        - Severe abdominal pain suggesting appendicitis
        - Seizures or convulsions
        - Choking, severe difficulty swallowing
        - Coughing up blood or severe vomiting of blood
        - Sudden, severe "thunderclap" headache
        - Major fractures with visible bone or severe deformity
        - Extreme psychiatric emergencies or altered mental state
        - Pregnancy complications (e.g., severe bleeding, signs of premature labor)
        - Any life-threatening condition

        NON-EMERGENCY (Respond with "normal"):
        - Mild symptoms (minor headache, cold, mild fever)
        - Chronic conditions without acute worsening
        - General health questions
        - Routine medical concerns
        - Mild pain or discomfort

        RESPONSE FORMAT:
        - MUST respond with exactly: "emergency" OR "normal"
        - No additional text or explanation

        SYMPTOM DESCRIPTION: "{user_input}"

        YOUR CLASSIFICATION:
        """

        try:
            response = gemini_client.models.generate_content(model=self.model, contents=prompt)
            result = re.sub(r"^```[a-zA-Z]*\n?|```$", "", response.text.strip(), flags=re.DOTALL)
            classification = result.lower().strip()

            if classification == "emergency":
                return {
                    "is_emergency": True,
                    "confidence": 0.8,
                    "trigger": "AI emergency classification",
                    "classification": "emergency"
                }
            else:
                return {
                    "is_emergency": False,
                    "confidence": 0.8,
                    "trigger": "Normal medical consultation",
                    "classification": "normal"
                }

        except Exception as e:
            print(f"Emergency classification error: {e}")
            # Default to non-emergency if AI fails
            return {
                "is_emergency": False,
                "confidence": 0.0,
                "trigger": "Classification failed - defaulted to normal",
                "classification": "error"
            }

    def make_emergency_call(self, to_number: str, message: str) -> bool:
        """Make emergency call using Twilio"""
        if not twilio_client:
            print("⚠️ Twilio not configured - cannot make emergency call")
            return False

        try:
            call = twilio_client.calls.create(
                to=to_number,
                from_=TWILIO_NUMBER,
                twiml=f'<Response><Say voice="alice">{message}</Say></Response>'
            )
            print(f"🚨 Emergency call initiated: {call.sid}")
            return True
        except Exception as e:
            print(f"❌ Emergency call failed: {e}")
            return False


class GeminiMedicalAnalyzer:
    """Medical analysis using Gemini AI instead of ML models"""

    def __init__(self):
        self.model = gemini_model
        # Initialize RAG components
        try:
            import chromadb
            from chromadb.utils import embedding_functions
            import os
            
            chroma_dir = os.getenv("CHROMA_DB_PATH", "chroma.sqlite3")
            self.chroma_client = chromadb.PersistentClient(path=chroma_dir)
            
            embedding_model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=embedding_model_name)
            
            self.collection = self.chroma_client.get_or_create_collection(name="medical_docs", embedding_function=self.ef)
            self.rag_enabled = True
            print("✅ RAG initialized successfully for GeminiMedicalAnalyzer")
        except Exception as e:
            print(f"⚠️ RAG initialization failed. Proceeding without RAG: {e}")
            self.rag_enabled = False


    def analyze_symptoms(self, user_input: str) -> dict:
        """Analyze symptoms and predict condition using Gemini"""
        
        rag_context = ""
        if self.rag_enabled:
            try:
                # Query the vector DB
                results = self.collection.query(
                    query_texts=[user_input],
                    n_results=3
                )
                if results and results['documents'] and results['documents'][0]:
                    chunks = results['documents'][0]
                    rag_context = "MEDICAL CONTEXT FROM ATTACHED DOCUMENTS:\n" + "\n---\n".join(chunks) + "\n\n"
            except Exception as e:
                print(f"RAG retrieval error: {e}")

        prompt = f"""
        You are an expert medical AI assistant. Analyze the following patient symptoms and provide a medical assessment.

        {rag_context}

        PATIENT INPUT: "{user_input}"
        
        If MEDICAL CONTEXT FROM ATTACHED DOCUMENTS is provided above, you MUST base your primary condition and recommended specialist strictly on that text.

        Please provide your analysis in the following JSON format:
        {{
            "extracted_symptoms": ["symptom1", "symptom2", "symptom3"],
            "primary_condition": "Most likely condition name",
            "confidence_level": "high/medium/low",
            "recommended_specialist": "Type of specialist needed",
            "urgency": "emergency/urgent/routine",
            "additional_questions": ["question1", "question2"],
            "general_advice": "Brief general medical advice"
        }}

        Guidelines:
        - Extract clear, medical symptoms from the input
        - Provide the most likely primary condition
        - Recommend appropriate medical specialist
        - Assess urgency level appropriately
        - Give helpful but not diagnostic advice
        - Ask relevant follow-up questions if needed

        Remember: This is for guidance only, not a medical diagnosis.
        """

        try:
            config = types.GenerateContentConfig(response_mime_type="application/json")
            response = gemini_client.models.generate_content(model=self.model, contents=prompt, config=config)
            analysis = json.loads(response.text)

            # Validate required fields
            required_fields = ["extracted_symptoms", "primary_condition", "recommended_specialist"]
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = "Unknown"

            return analysis

        except Exception as e:
            print(f"Medical analysis error: {e}")
            return {
                "extracted_symptoms": ["unspecified symptoms"],
                "primary_condition": "Unable to determine",
                "confidence_level": "low",
                "recommended_specialist": "General Physician",
                "urgency": "routine",
                "additional_questions": ["Could you describe your symptoms more clearly?"],
                "general_advice": "Please consult with a healthcare professional for proper evaluation."
            }


# Initialize components
emergency_classifier = EmergencyClassifier()
medical_analyzer = GeminiMedicalAnalyzer()


def get_db_connection():
    """Get database connection with error handling"""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT")
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected database error: {e}")
        return None


def log_emergency_event(user_input: str, classification_result: dict, call_success: bool = None):
    """Log emergency detection events for audit"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "classification": classification_result,
            "call_made": call_success,
            "emergency_number": EMERGENCY_NUMBER if call_success else None
        }

        # Log to file (you could also log to database)
        log_file = "emergency_logs.json"
        logs = []
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)

        logs.append(log_entry)

        # Keep only last 1000 entries
        if len(logs) > 1000:
            logs = logs[-1000:]

        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)

    except Exception as e:
        print(f"Error logging emergency event: {e}")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "HealthVerse AI Backend",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0",
        "ai_system": "Gemini-powered",
        "emergency_system": "enabled" if twilio_client else "disabled"
    })


@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint with emergency detection and Gemini analysis"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        user_input = data.get('message', '').strip()
        session_id = data.get('session_id') or str(uuid.uuid4())

        if not user_input:
            return jsonify({"error": "Empty message"}), 400

        # EMERGENCY DETECTION FIRST
        emergency_result = emergency_classifier.is_emergency(user_input)

        if emergency_result["is_emergency"]:
            print(f"🚨 EMERGENCY DETECTED: {emergency_result['trigger']}")

            # Make emergency call
            call_message = f"Emergency alert from HealthVerse AI. A patient has reported: {user_input[:100]}. Please dispatch emergency services immediately."
            call_success = emergency_classifier.make_emergency_call(EMERGENCY_NUMBER, call_message)

            # Log the emergency event
            log_emergency_event(user_input, emergency_result, call_success)

            emergency_response = {
                "response_text": "🚨 **MEDICAL EMERGENCY DETECTED** 🚨\n\n" +
                                 "I've automatically contacted emergency services for you.\n\n" +
                                 "**IMMEDIATE ACTIONS:**\n" +
                                 "• Call 108 (Ambulance) immediately if you haven't already\n" +
                                 "• If experiencing chest pain: Chew aspirin if not allergic\n" +
                                 "• Stay calm and don't move unless absolutely necessary\n" +
                                 "• Have someone stay with you if possible\n\n" +
                                 "Emergency services have been notified. Help is on the way.",
                "session_id": session_id,
                "emergency_detected": True,
                "emergency_call_made": call_success,
                "next_action": "emergency_protocol"
            }

            return jsonify(emergency_response)

        # Continue with Gemini medical analysis if not emergency
        medical_analysis = medical_analyzer.analyze_symptoms(user_input)

        if not medical_analysis.get("extracted_symptoms") or medical_analysis[
            "primary_condition"] == "Unable to determine":
            return jsonify({
                "response_text": "I couldn't clearly identify your symptoms. Could you please describe them more specifically? For example: 'I have fever, headache, and sore throat'",
                "session_id": session_id,
                "next_action": "ask_more",
                "emergency_detected": False
            })

        # Get specialist from analysis
        specialist = medical_analysis.get("recommended_specialist", "General Physician")
        primary_condition = medical_analysis.get("primary_condition", "Unknown condition")
        symptoms = medical_analysis.get("extracted_symptoms", [])

        # Get doctors from database
        doctor_list = []
        conn = get_db_connection()

        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                                   SELECT d.doctor_id,
                                          d.first_name,
                                          d.last_name,
                                          h.name,
                                          COALESCE(d.average_rating, 4.0) as rating,
                                          h.latitude,
                                          h.longitude
                                   FROM Doctors d
                                            JOIN Hospitals h ON d.hospital_id = h.hospital_id
                                            JOIN Doctor_Specializations ds ON d.doctor_id = ds.doctor_id
                                            JOIN Specializations s ON ds.specialization_id = s.specialization_id
                                   WHERE s.specialization_name ILIKE %s
                                   ORDER BY d.average_rating DESC NULLS LAST, d.doctor_id
                                       LIMIT 3;
                                   """, (f"%{specialist}%",))

                    doctors_data = cursor.fetchall()

                    for doc in doctors_data:
                        doc_id, first_name, last_name, hospital_name, rating, lat, lon = doc

                        # Generate sample slots (simplified)
                        slots = []
                        for hour in range(9, 17, 2):  # 9 AM to 5 PM, every 2 hours
                            am_pm = "AM" if hour < 12 else "PM"
                            display_hour = hour if hour <= 12 else hour - 12
                            slots.append(f"{display_hour}:00 {am_pm}")
                            slots.append(f"{display_hour}:30 {am_pm}")

                        if slots:  # Only add doctors with available slots
                            doctor_list.append({
                                "id": doc_id,
                                "name": f"{first_name} {last_name}",
                                "hospital": hospital_name,
                                "rating": float(rating),
                                "slots": slots[:4],  # Limit to 4 slots
                                "latitude": lat,
                                "longitude": lon
                            })

            except Exception as e:
                print(f"Database query error: {e}")
            finally:
                conn.close()

        # Build response with AI analysis
        confidence_text = f"(Confidence: {medical_analysis.get('confidence_level', 'medium')})"
        response_text = f"Based on your symptoms ({', '.join(symptoms)}), the likely condition is **{primary_condition}** {confidence_text}.\n\nRecommended specialist: **{specialist}**"

        # Add general advice if available
        if medical_analysis.get('general_advice'):
            response_text += f"\n\n**General Advice:** {medical_analysis['general_advice']}"

        # Add follow-up questions if available
        if medical_analysis.get('additional_questions'):
            questions = medical_analysis['additional_questions'][:2]  # Limit to 2 questions
            response_text += f"\n\n**Additional Questions:** {' '.join(questions)}"

        if doctor_list:
            response_text += f"\n\nHere are available {specialist}s:"
            for i, doc in enumerate(doctor_list):
                response_text += f"\n\n{i + 1}. **Dr. {doc['name']}** at {doc['hospital']}"
                response_text += f"\n   Rating: {doc['rating']:.1f}⭐"
                response_text += f"\n   Available today: {', '.join(doc['slots'])}"

            response_text += "\n\nClick on any time slot above to book an appointment!"
        else:
            response_text += f"\n\nSorry, no {specialist}s are currently available. Please try again later or contact us directly."

        return jsonify({
            "response_text": response_text,
            "session_id": session_id,
            "symptoms": symptoms,
            "predicted_condition": primary_condition,
            "specialist": specialist,
            "doctors": doctor_list,
            "emergency_detected": False,
            "ai_analysis": medical_analysis,
            "next_action": "book_appointment" if doctor_list else "no_doctors"
        })

    except Exception as e:
        print(f"Chat endpoint error: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": "I'm experiencing technical difficulties. Please try again."
        }), 500


@app.route('/emergency-check', methods=['POST'])
def emergency_check():
    """Dedicated endpoint for emergency detection"""
    try:
        data = request.json
        user_input = data.get('message', '').strip()

        if not user_input:
            return jsonify({"error": "No message provided"}), 400

        result = emergency_classifier.is_emergency(user_input)

        if result["is_emergency"]:
            # Log the emergency
            log_emergency_event(user_input, result)

            return jsonify({
                "is_emergency": True,
                "confidence": result["confidence"],
                "trigger": result["trigger"],
                "recommendation": "Call 108 immediately or proceed to nearest emergency room"
            })
        else:
            return jsonify({
                "is_emergency": False,
                "confidence": result["confidence"],
                "recommendation": "Proceed with normal consultation"
            })

    except Exception as e:
        print(f"Emergency check error: {e}")
        return jsonify({"error": "Emergency detection service error"}), 500


@app.route('/trigger-emergency-call', methods=['POST'])
def trigger_emergency_call():
    """Manually trigger emergency call (for testing or explicit requests)"""
    try:
        data = request.json
        message = data.get('message', 'Emergency assistance requested through HealthVerse AI')
        to_number = data.get('to_number', EMERGENCY_NUMBER)

        if not twilio_client:
            return jsonify({"error": "Emergency call service not configured"}), 503

        call_success = emergency_classifier.make_emergency_call(to_number, message)

        if call_success:
            return jsonify({
                "success": True,
                "message": "Emergency call initiated successfully",
                "called_number": to_number
            })
        else:
            return jsonify({
                "success": False,
                "message": "Failed to initiate emergency call"
            }), 500

    except Exception as e:
        print(f"Manual emergency call error: {e}")
        return jsonify({"error": "Emergency call service error"}), 500


@app.route('/parse-booking-intent', methods=['POST'])
def parse_booking_intent():
    """Parse booking requests using Gemini"""
    try:
        data = request.json
        user_input = data.get('user_input', '')
        doctors = data.get('doctors', [])

        if not user_input or not doctors:
            return jsonify({"error": "Missing booking data"}), 400

        # Create doctor options text for LLM
        doctor_options = "\n".join([
            f"Doctor {i + 1}: Dr. {doc['name']} at {doc['hospital']} (ID: {doc['id']}) - Available: {', '.join(doc['slots'])}"
            for i, doc in enumerate(doctors)
        ])

        prompt = f"""
        Parse this booking request and extract the doctor ID and time slot.

        Available doctors and slots:
        {doctor_options}

        User request: "{user_input}"

        Return JSON format:
        {{
            "doctor_id": <extracted_doctor_id_or_null>,
            "slot": <extracted_time_slot_or_null>,
            "doctor_name": <doctor_name_if_found>,
            "time_str": <formatted_time_string>,
            "clarification": <question_to_ask_if_unclear>
        }}
        """

        config = types.GenerateContentConfig(response_mime_type="application/json")
        response = gemini_client.models.generate_content(model=gemini_model, contents=prompt, config=config)
        parsed_result = json.loads(response.text)

        return jsonify(parsed_result)

    except Exception as e:
        print(f"Booking intent parsing error: {e}")
        return jsonify({
            "doctor_id": None,
            "slot": None,
            "clarification": "I couldn't understand your booking request. Please specify which doctor and time slot you prefer."
        })


@app.route('/book', methods=['POST'])
def book_appointment():
    """Book appointment endpoint"""
    try:
        data = request.json
        patient_phone = data.get('patient_phone')
        doctor_id = data.get('doctor_id')
        slot_iso = data.get('slot')
        reason = data.get('reason', 'Medical consultation')
        disease = data.get('disease', 'Unknown')

        if not all([patient_phone, doctor_id, slot_iso]):
            return jsonify({"error": "Missing required booking information"}), 400

        try:
            slot_dt = datetime.fromisoformat(slot_iso.replace('Z', '+00:00'))
        except:
            return jsonify({"error": "Invalid time format"}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database service unavailable"}), 503

        try:
            with conn.cursor() as cur:
                # Create or find patient
                cur.execute("SELECT patient_id FROM Patients WHERE phone_number=%s;", (patient_phone,))
                result = cur.fetchone()

                if result:
                    patient_id = result[0]
                else:
                    # Create new patient
                    cur.execute("""
                                INSERT INTO Patients (first_name, last_name, phone_number, created_at)
                                VALUES (%s, %s, %s, NOW()) RETURNING patient_id;
                                """, ('New', 'Patient', patient_phone))
                    patient_id = cur.fetchone()[0]

                # Check slot availability
                cur.execute("""
                            SELECT 1
                            FROM Appointments
                            WHERE doctor_id = %s
                              AND appointment_time = %s
                              AND status IN ('Scheduled', 'Booked');
                            """, (doctor_id, slot_dt))

                if cur.fetchone():
                    return jsonify({"error": "This time slot is no longer available"}), 409

                # Book appointment
                cur.execute("""
                            INSERT INTO Appointments
                            (patient_id, doctor_id, hospital_id, appointment_time, reason_for_visit,
                             ai_predicted_disease, status, created_at)
                            VALUES (%s, %s, (SELECT hospital_id FROM Doctors WHERE doctor_id = %s), %s, %s, %s,
                                    'Scheduled', NOW()) RETURNING appointment_id;
                            """, (patient_id, doctor_id, doctor_id, slot_dt, reason, disease))

                appointment_id = cur.fetchone()[0]

                # Get hospital details
                cur.execute("""
                            SELECT h.name, h.latitude, h.longitude, d.first_name, d.last_name
                            FROM Hospitals h
                                     JOIN Doctors d ON h.hospital_id = d.hospital_id
                            WHERE d.doctor_id = %s;
                            """, (doctor_id,))

                hospital_data = cur.fetchone()
                conn.commit()

                return jsonify({
                    "message": f"Appointment confirmed! ID: {appointment_id}",
                    "hospital_name": hospital_data[0],
                    "latitude": float(hospital_data[1]),
                    "longitude": float(hospital_data[2]),
                    "doctor_name": f"Dr. {hospital_data[3]} {hospital_data[4]}"
                }), 201

        except Exception as e:
            conn.rollback()
            print(f"Booking error: {e}")
            return jsonify({"error": "Booking failed due to database error"}), 500
        finally:
            conn.close()

    except Exception as e:
        print(f"Book endpoint error: {e}")
        return jsonify({"error": "Booking service error"}), 500


@app.route('/directions', methods=['POST'])
def get_directions():
    """Get directions to hospital"""
    try:
        data = request.json
        user_lat = data.get('user_lat')
        user_lon = data.get('user_lon')
        dest_lat = data.get('dest_lat')
        dest_lon = data.get('dest_lon')

        if not all([user_lat, user_lon, dest_lat, dest_lon]):
            return jsonify({"error": "Missing coordinates"}), 400

        directions_url = f"https://www.google.com/maps/dir/?api=1&origin={user_lat},{user_lon}&destination={dest_lat},{dest_lon}&travelmode=driving"

        return jsonify({"directions_url": directions_url})

    except Exception as e:
        print(f"Directions error: {e}")
        return jsonify({"error": "Failed to generate directions"}), 500


@app.route('/emergency-logs', methods=['GET'])
def get_emergency_logs():
    """Get emergency detection logs (for admin dashboard)"""
    try:
        log_file = "emergency_logs.json"
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                logs = json.load(f)
            return jsonify({"logs": logs[-50:]})  # Return last 50 entries
        else:
            return jsonify({"logs": []})
    except Exception as e:
        print(f"Error retrieving emergency logs: {e}")
        return jsonify({"error": "Could not retrieve logs"}), 500


# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    print("🏥 HealthVerse AI Backend Server Starting...")
    print("🧠 AI System: Gemini-powered medical analysis")
    print(f"🚨 Emergency System: {'Enabled' if twilio_client else 'Disabled'}")
    print(f"📞 Emergency Number: {EMERGENCY_NUMBER}")
    print(f"🔗 Running on: http://localhost:8080")
    print("📡 Endpoints: /health, /chat, /book, /directions, /emergency-check, /trigger-emergency-call")

    app.run(host="0.0.0.0", port=8080, debug=True)
