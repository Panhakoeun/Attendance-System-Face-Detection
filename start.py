import os
import sys

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Now import and run the app
from face_attendance.app import app

if __name__ == "__main__":
    print("Starting the application...")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Template directory: {os.path.join(os.path.dirname(__file__), 'face_attendance', 'templates')}")
    print(f"Static directory: {os.path.join(os.path.dirname(__file__), 'face_attendance', 'static')}")
    
    # Run the app with debug mode on
    app.run(debug=True, host='0.0.0.0', port=5000)
