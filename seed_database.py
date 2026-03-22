import os
import psycopg2
from dotenv import load_dotenv

def seed_database():
    load_dotenv()
    print("⏳ Connecting to the database...")
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432")
        )
        cur = conn.cursor()

        # 1. Insert Specializations
        specializations = [
            "General Physician", "Cardiologist", "Pulmonologist", "Neurologist", 
            "Gastroenterologist", "Dermatologist", "Orthopedist", "Psychiatrist", 
            "Endocrinologist", "Pediatrician", "Oncologist", "Gynecologist", 
            "ENT Specialist", "Ophthalmologist", "Urologist", "Allergist",
            "Rheumatologist", "Nephrologist", "General Practitioner"
        ]
        
        print("💉 Inserting Specializations...")
        for spec in specializations:
            cur.execute("SELECT specialization_id FROM Specializations WHERE specialization_name = %s", (spec,))
            if not cur.fetchone():
                cur.execute("INSERT INTO Specializations (specialization_name) VALUES (%s)", (spec,))
        
        cur.execute("SELECT specialization_id, specialization_name FROM Specializations")
        spec_map = {name: sid for sid, name in cur.fetchall()}

        # 2. Insert Hospitals
        hospitals = [
            ("Apollo Hospitals", 17.4165, 78.4140),
            ("Care Hospitals", 17.4208, 78.4418),
            ("Yashoda Hospitals", 17.4285, 78.4556),
            ("KIMS Hospitals", 17.4334, 78.4878),
            ("Rainbow Children's Hospital", 17.4259, 78.4485),
            ("AIG Hospitals", 17.4435, 78.3610),
            ("Medicover Hospitals", 17.4475, 78.3754)
        ]
        print("🏥 Inserting Hospitals...")
        for h_name, lat, lon in hospitals:
            cur.execute("SELECT hospital_id FROM Hospitals WHERE name = %s", (h_name,))
            if not cur.fetchone():
                cur.execute("INSERT INTO Hospitals (name, latitude, longitude) VALUES (%s, %s, %s)", (h_name, lat, lon))
        
        cur.execute("SELECT hospital_id, name FROM Hospitals")
        hosp_map = {name: hid for hid, name in cur.fetchall()}

        # 3. Insert Doctors
        doctors_data = [
            ("Ramesh", "Kumar", "Apollo Hospitals", 4.9, ["Cardiologist", "General Physician"]),
            ("Sita", "Reddy", "Apollo Hospitals", 4.7, ["Neurologist"]),
            ("Arun", "Sharma", "Care Hospitals", 4.8, ["Pulmonologist", "Allergist"]),
            ("Priya", "Menon", "Care Hospitals", 4.5, ["Dermatologist"]),
            ("Vikram", "Singh", "Yashoda Hospitals", 4.6, ["Orthopedist"]),
            ("Anita", "Desai", "Yashoda Hospitals", 4.9, ["Gastroenterologist", "General Physician"]),
            ("Rahul", "Verma", "KIMS Hospitals", 4.7, ["Endocrinologist"]),
            ("Neha", "Gupta", "KIMS Hospitals", 4.8, ["Psychiatrist"]),
            ("Sanjay", "Patil", "Rainbow Children's Hospital", 4.9, ["Pediatrician"]),
            ("Pooja", "Joshi", "Rainbow Children's Hospital", 4.6, ["Gynecologist"]),
            ("Kiran", "Narayan", "AIG Hospitals", 4.8, ["Gastroenterologist", "Oncologist"]),
            ("Deepak", "Chopra", "AIG Hospitals", 4.7, ["Urologist"]),
            ("Meera", "Rao", "Medicover Hospitals", 4.9, ["ENT Specialist"]),
            ("Anand", "Iyer", "Medicover Hospitals", 4.8, ["Ophthalmologist"]),
            ("Rajesh", "Nair", "Apollo Hospitals", 4.6, ["Nephrologist", "General Physician"]),
            ("Sunita", "Mishra", "Care Hospitals", 4.5, ["Rheumatologist"]),
            ("Aruna", "Das", "Medicover Hospitals", 4.7, ["General Practitioner"])
        ]
        
        print("🩺 Inserting Doctors and their Specializations...")
        for fname, lname, hname, rating, specs in doctors_data:
            hid = hosp_map.get(hname)
            if not hid: continue
            
            cur.execute("SELECT doctor_id FROM Doctors WHERE first_name = %s AND last_name = %s", (fname, lname))
            doc = cur.fetchone()
            
            if not doc:
                cur.execute("""
                    INSERT INTO Doctors (first_name, last_name, hospital_id, average_rating)
                    VALUES (%s, %s, %s, %s) RETURNING doctor_id
                """, (fname, lname, hid, rating))
                doc_id = cur.fetchone()[0]
                
                for spec_name in specs:
                    sid = spec_map.get(spec_name)
                    if sid:
                        cur.execute("""
                            INSERT INTO Doctor_Specializations (doctor_id, specialization_id)
                            VALUES (%s, %s)
                        """, (doc_id, sid))

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Database successfully seeded with comprehensive sample data!")

    except Exception as e:
        print(f"❌ Error seeding database: {e}")

if __name__ == "__main__":
    seed_database()
