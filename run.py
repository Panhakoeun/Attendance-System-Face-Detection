from face_attendance.app import app
import os

if __name__ == '__main__':
    # Ensure the uploads directory exists
    uploads_dir = os.path.join(os.path.dirname(__file__), 'face_attendance', 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Run the app with debug mode and proper host/port
    app.run(
        debug=True,
        host='0.0.0.0',  # Allow connections from any network interface
        port=5001,
        use_reloader=True
    )
