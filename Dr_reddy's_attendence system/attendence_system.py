import cv2
import numpy as np
import os
import sqlite3
import pandas as pd
import face_recognition
from datetime import datetime, timedelta

# ---------- Constants & Setup ----------
DB_PATH = 'database/attendance.db'
FACE_DIR = 'static/faces'
LOG_DIR = 'attendance_logs'

os.makedirs('database', exist_ok=True)
os.makedirs(FACE_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ---------- Initialize Database ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            department TEXT,
            batch TEXT DEFAULT '2',
            image_path TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            login_time TEXT,
            logout_time TEXT,
            duration TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# ---------- Register User ----------
def register_user(name, email, department, batch):
    cam = cv2.VideoCapture(0)
    print("📷 Capturing face. Press 's' to save.")
    while True:
        ret, frame = cam.read()
        if not ret:
            print("❌ Failed to access camera.")
            break
        cv2.imshow("Register Face", frame)
        if cv2.waitKey(1) & 0xFF == ord('s'):
            image_path = os.path.join(FACE_DIR, f'{name}.jpg')
            cv2.imwrite(image_path, frame)
            print(f"✅ Face saved at {image_path}")
            break
    cam.release()
    cv2.destroyAllWindows()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (name, email, department, batch, image_path) VALUES (?, ?, ?, ?, ?)",
              (name, email, department, batch, image_path))
    conn.commit()
    conn.close()
    print("✅ User registered successfully.")

# ---------- Load Known Faces ----------
def load_known_faces():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, name, image_path FROM users")
    users = c.fetchall()
    conn.close()

    encodings, names, ids = [], [], []
    for user_id, name, path in users:
        try:
            image = face_recognition.load_image_file(path)
            encoding = face_recognition.face_encodings(image)[0]
            encodings.append(encoding)
            names.append(name)
            ids.append(user_id)
        except Exception as e:
            print(f"⚠️ Error encoding face for {name}: {e}")
    return encodings, names, ids

# ---------- Attendance Functions ----------
def get_attendance_entry(user_id, date):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, login_time, logout_time FROM attendance WHERE user_id=? AND date=?", (user_id, date))
    entry = c.fetchone()
    conn.close()
    return entry

def insert_login(user_id, date, login_time):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO attendance (user_id, date, login_time) VALUES (?, ?, ?)", (user_id, date, login_time))
    conn.commit()
    conn.close()

def update_logout(user_id, date, logout_time):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT login_time FROM attendance WHERE user_id=? AND date=?", (user_id, date))
    login_time = c.fetchone()
    if login_time:
        login_dt = datetime.strptime(login_time[0], "%H:%M:%S")
        logout_dt = datetime.strptime(logout_time, "%H:%M:%S")
        duration = str(logout_dt - login_dt)
        c.execute("UPDATE attendance SET logout_time=?, duration=? WHERE user_id=? AND date=?",
                  (logout_time, duration, user_id, date))
        print(f"🕒 Updated logout time for user_id={user_id} at {logout_time}, duration: {duration}")
    conn.commit()
    conn.close()

# ---------- Export to Excel ----------
def export_attendance_to_excel():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('''
        SELECT u.name, u.email, u.department, u.batch, a.date, a.login_time, a.logout_time, a.duration
        FROM attendance a
        JOIN users u ON a.user_id = u.id
    ''', conn)
    conn.close()

    # Compute status column
    def determine_status(row):
        if pd.isna(row['logout_time']) or row['logout_time'] is None:
            return "Incomplete"
        try:
            h, m, s = map(int, str(row['duration']).split(':'))
            total_minutes = h * 60 + m + s / 60
            return "Present" if total_minutes >= 240 else "Left Early"
        except:
            return "Invalid Duration"

    df['status'] = df.apply(determine_status, axis=1)

    filename = f"attendance_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    filepath = os.path.join(LOG_DIR, filename)
    df.to_excel(filepath, index=False, engine='openpyxl')
    print(f"📄 Attendance exported to {filepath}")
    return filepath


# ---------- Real-Time Face Recognition ----------
def recognize_faces():
    print("🚀 Starting Attendance Recognition. Press 'q' to quit.")
    known_encodings, known_names, known_ids = load_known_faces()
    if not known_encodings:
        print("❌ No known faces found. Register users first.")
        return

    last_seen = {}
    timeout = timedelta(minutes=1)
    cap = cv2.VideoCapture(0)

    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame.")
            break
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        locations = face_recognition.face_locations(rgb)
        encodings = face_recognition.face_encodings(rgb, locations)

        for encode, loc in zip(encodings, locations):
            matches = face_recognition.compare_faces(known_encodings, encode)
            face_dist = face_recognition.face_distance(known_encodings, encode)
            match_index = np.argmin(face_dist)

            if matches[match_index]:
                name = known_names[match_index]
                user_id = known_ids[match_index]
                now = datetime.now()
                date, time = now.strftime('%Y-%m-%d'), now.strftime('%H:%M:%S')

                if user_id not in last_seen or now - last_seen[user_id] > timeout:
                    entry = get_attendance_entry(user_id, date)
                    if not entry:
                        insert_login(user_id, date, time)
                        print(f"✅ {name} logged in at {time}")
                    elif entry[2] is None:
                        update_logout(user_id, date, time)
                        print(f"✅ {name} logged out at {time}")
                    last_seen[user_id] = now

                # Draw bounding box
                y1, x2, y2, x1 = loc
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, name, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        cv2.imshow("Face Recognition Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

# ---------- Main Menu ----------
def main_menu():
    init_db()  # Ensure database is initialized

    while True:
        print("\n=== Facial Recognition Attendance System ===")
        print("1. Register New User")
        print("2. Take Attendance")
        print("3. Export Attendance to Excel")
        print("4. Exit")

        choice = input("Enter your choice (1-4): ").strip()

        if choice == '1':
            name = input("Enter name: ").strip()
            email = input("Enter email: ").strip()
            department = input("Enter department: ").strip()
            batch = input("Enter batch (e.g., 2023, A, etc.): ").strip()
            register_user(name, email, department, batch)

        elif choice == '2':
            recognize_faces()

        elif choice == '3':
            export_attendance_to_excel()

        elif choice == '4':
            print("👋 Exiting the system. Goodbye!")
            break

        else:
            print("❌ Invalid choice. Please try again.")

        again = input("\nDo you want to continue? (y/n): ").strip().lower()
        if again != 'y':
            print("👋 Exiting the system. Goodbye!")
            break

# ---------- Entry Point ----------
if __name__ == "__main__":
    main_menu()
