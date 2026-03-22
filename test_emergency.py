import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_NUMBER")
emergency_number = os.getenv("EMERGENCY_NUMBER")

print("Testing Twilio emergency caller...")
try:
    client = Client(account_sid, auth_token)
    call = client.calls.create(
        to=emergency_number,
        from_=twilio_number,
        twiml='<Response><Say>Test call from HealthVerse AI</Say></Response>'
    )
    print(f"Success! Call SID: {call.sid}")
except Exception as e:
    print(f"Error: {e}")