# Face Attendance System

A modern attendance tracking system using facial recognition technology. This system allows for automated attendance recording through face detection and recognition.

## Features

- Real-time face detection and recognition
- Automatic attendance logging
- User enrollment system
- Web-based interface
- Individual attendance records per user
- Export attendance data
- Multiple face database support

## Prerequisites

- Python 3.10 or higher
- Webcam access
- Required Python packages (listed in requirements.txt)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Panhakoeun/Attendance-System-Face-Detection.git
cd Attendance-System-Face-Detection
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
# On Windows
.venv\Scripts\activate
# On Linux/Mac
source .venv/bin/activate
```

3. Install the required packages:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the application:
```bash
python run.py
```

2. Access the web interface:
   - Open your browser and navigate to `http://localhost:5001`
   - For external access: `http://<your-computer-ip>:5001`

### Enrolling New Users

1. Prepare a clear face photo of the user
2. Navigate to the enrollment page
3. Upload the photo and enter the user's name
4. Submit to add the user to the system

### Taking Attendance

1. Launch the application
2. The system will automatically detect and recognize faces
3. Attendance is logged automatically when a recognized face is detected
4. View attendance records in the web interface

## Project Structure

```
face_attendance/
├── app.py              # Main Flask application
├── enroll.py           # User enrollment functionality
├── utils.py           # Utility functions
├── data/              # Attendance data storage
│   ├── attendance.csv
│   └── attendance_users/
├── known_faces/       # Enrolled user face images
├── static/            # Static web assets
├── templates/         # HTML templates
└── uploads/           # Temporary image uploads
```

## Configuration

- Default port: 5001
- Face detection threshold can be adjusted in the configuration
- Attendance logging interval: Configurable per user
- Supports multiple file formats for face images (JPG, PNG)

## Troubleshooting

1. If the webcam doesn't start:
   - Check camera permissions
   - Ensure no other application is using the camera

2. If face recognition isn't working:
   - Ensure proper lighting
   - Check if the face is clearly visible
   - Verify that the user is enrolled in the system

3. If the application won't start:
   - Verify all dependencies are installed
   - Check if the port 5001 is available
   - Ensure Python environment is properly activated

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Face recognition powered by face_recognition library
- Web interface built with Flask
- Special thanks to all contributors