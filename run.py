from face_attendance.app import app

if __name__ == '__main__':
    # Using a different port to avoid conflicts
    app.run(
        debug=True,  # Enabling debug mode temporarily for testing
        host='localhost',  # Binding specifically to localhost
        port=5001  # Using a different port
    )
