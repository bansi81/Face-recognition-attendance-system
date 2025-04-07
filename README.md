# Face Recognition Attendance System

A comprehensive web-based attendance management system using facial recognition technology. Built with Flask, OpenCV, and PostgreSQL.

## Features

- **Facial Recognition**: Secure biometric attendance using Viola-Jones detection with Haar Cascades and a hybrid LBP+HOG approach for feature extraction
- **Multi-Course Support**: Register students across multiple courses with flexible enrollment options
- **Anti-Spoofing**: Enhanced security with strict matching thresholds to prevent proxy attendance
- **User Management**: Add, edit, and remove students with their course enrollments
- **Reporting**: Comprehensive attendance reports and statistics
- **User Authentication**: Secure login with password reset functionality via security questions

## Technology Stack

- **Backend**: Python, Flask
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Face Recognition**: OpenCV with Haar Cascades and hybrid feature extraction
- **Frontend**: HTML, CSS, JavaScript, Bootstrap

## Installation

1. Clone the repository

   git clone https://github.com/bansi81/face-recognition-attendance-system.git
   cd face-recognition-attendance-system


2. Install dependencies

   pip install -r requirements.txt


3. Set up environment variables
   
   Create a `.env` file in the root directory with the following:

   DATABASE_URL=postgresql://username:root@localhost:5432/attendance_db
   SESSION_SECRET=your_secret_key


4. Initialize the database

   python -c "from app import db; db.create_all()


5. Run the application

   python main.py


6. Access the application
   
   Open your browser and navigate to `http://localhost:5000`

## Usage

### User Authentication
- Register a new account
- Login with your credentials
- Reset password using security questions if forgotten

### Managing Students
- Add new students with their details
- Register student faces for attendance
- Edit student information and course enrollments
- Remove students from the system

### Managing Courses
- Create new courses
- Assign students to courses
- View course attendance statistics

### Taking Attendance
- Select a course
- Capture student faces via webcam
- System automatically marks attendance for recognized students

### Viewing Reports
- Access attendance reports by date, course, or student
- Export attendance data as needed

## Database Schema

The system uses a relational database with the following main tables:
- Users: System users with authentication details
- Students: Student information including face encodings
- Courses: Course details 
- Attendances: Attendance records linking students and courses

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
