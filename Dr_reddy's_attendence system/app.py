from flask import Flask, render_template, request, redirect, url_for, flash, Response
from attendence_system import (
    init_db, register_user, recognize_faces, export_attendance_to_excel
)
import os
import cv2

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize DB
init_db()

# Camera for video feed
camera = cv2.VideoCapture(0)

def gen_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        department = request.form['department']
        batch = request.form['batch']
        if name and department:
            register_user(name, email, department, batch)
            flash(f"{name} registered successfully!", 'success')
            return redirect(url_for('home'))
        else:
            flash("Name and Department are required.", 'error')
    return render_template('register.html')

@app.route('/take_attendance')
def take_attendance():
    filepath = recognize_faces()
    if filepath:
        flash(f"Attendance saved to {filepath}", 'success')
    else:
        flash("No faces recognized.", 'info')
    return redirect(url_for('home'))

@app.route('/export')
def export():
    filepath = export_attendance_to_excel()
    if filepath:
        flash(f"Attendance exported to: {os.path.abspath(filepath)}", 'success')
    else:
        flash("No attendance records to export.", 'error')
    return redirect(url_for('home'))

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/exit')
def exit_page():
    return render_template('exit.html')


if __name__ == '__main__':
    app.run(debug=True)
