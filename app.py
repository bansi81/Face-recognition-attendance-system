import os
import logging
from datetime import datetime
import numpy as np
import cv2
from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import base64
from io import BytesIO
import json
from face_utils import process_and_encode_face, recognize_faces, process_image_data, detect_face, extract_face_features

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy
db = SQLAlchemy(model_class=Base)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "default_secret_key")

# Database configuration for PostgreSQL only
logger.info("Using PostgreSQL database exclusively")

# Get PostgreSQL connection details from environment variables
pg_url = os.environ.get("DATABASE_URL")
if not pg_url:
    # If DATABASE_URL is not set, construct it from individual connection parameters
    pg_host = os.environ.get("PGHOST", "localhost") 
    pg_port = os.environ.get("PGPORT", "5432")
    pg_user = os.environ.get("PGUSER", "postgres")
    pg_password = os.environ.get("PGPASSWORD", "root")
    pg_database = os.environ.get("PGDATABASE", "postgres")
    
    pg_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_database}"
    logger.info(f"Constructed PostgreSQL URL from environment variables (host: {pg_host})")
else:
    # Fix the URL format if needed
    if pg_url.startswith("postgres://"):
        pg_url = pg_url.replace("postgres://", "postgresql://", 1)
    logger.info("Using PostgreSQL URL from DATABASE_URL environment variable")

# Set the database URL
database_url = pg_url
logger.info("PostgreSQL database configuration complete")

# Configure the application's database URI
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
logger.info(f"Database URL configured (without showing credential details)")

app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize database with app
db.init_app(app)

# Import face utils
from face_utils import process_and_encode_face, recognize_faces

# Initialize models and create tables within app context
with app.app_context():
    # Import models here to avoid circular imports
    from models import User, Student, Course, Attendance
    db.create_all()
    
    # Add missing columns if they don't exist
    try:
        from sqlalchemy import text
        sql = text("""
        ALTER TABLE users 
        ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100),
        ADD COLUMN IF NOT EXISTS reset_token_expiry TIMESTAMP,
        ADD COLUMN IF NOT EXISTS security_question VARCHAR(100),
        ADD COLUMN IF NOT EXISTS security_answer VARCHAR(100)
        """)
        db.session.execute(sql)
        db.session.commit()
        logger.info("Added security question and reset token columns to users table")
    except Exception as e:
        logger.error(f"Error adding columns to users table: {str(e)}")
        # Since we're in app context, this is safe
        db.session.rollback()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user or not check_password_hash(user.password_hash, password):
            error = 'Invalid email or password. Please try again.'
        else:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
    
    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        security_question = request.form.get('security_question')
        security_answer = request.form.get('security_answer')
        
        # Validate email format
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            error = 'Invalid email format. Please enter a valid email address.'
            return render_template('register.html', error=error)
            
        # Validate password strength
        if len(password) < 8:
            error = 'Password must be at least 8 characters long.'
            return render_template('register.html', error=error)
            
        # Check for password complexity
        if not any(char.isdigit() for char in password):
            error = 'Password must contain at least one number.'
            return render_template('register.html', error=error)
            
        if not any(char.isupper() for char in password):
            error = 'Password must contain at least one uppercase letter.'
            return render_template('register.html', error=error)
            
        if not any(char.islower() for char in password):
            error = 'Password must contain at least one lowercase letter.'
            return render_template('register.html', error=error)
            
        if not any(char in '!@#$%^&*()-_=+[]{}|;:,.<>?/~`' for char in password):
            error = 'Password must contain at least one special character.'
            return render_template('register.html', error=error)
        
        # Validate security answer
        if not security_answer or len(security_answer.strip()) < 2:
            error = 'Security answer is required and must be at least 2 characters.'
            return render_template('register.html', error=error)
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            error = 'Email already registered. Please login or use a different email.'
        else:
            new_user = User(
                username=username,
                email=email,
                password_hash=generate_password_hash(password),
                security_question=security_question,
                security_answer=security_answer.lower()  # Store answer in lowercase for easier matching
            )
            try:
                db.session.add(new_user)
                db.session.commit()
                
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                logger.error(f"Error registering user: {str(e)}")
                db.session.rollback()
                error = f"Database error: {str(e)}"
    
    return render_template('register.html', error=error)
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get counts for dashboard statistics
        student_count = Student.query.count()
        course_count = Course.query.count()
        
        # Get today's attendance count
        today = datetime.now().date()
        today_attendance = Attendance.query.filter(
            db.func.date(Attendance.timestamp) == today
        ).count()
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        student_count = 0
        course_count = 0
        today_attendance = 0
        flash("Error retrieving statistics", "danger")
    
    return render_template('dashboard.html', 
                           student_count=student_count,
                           course_count=course_count,
                           today_attendance=today_attendance)

@app.route('/students', methods=['GET', 'POST'])
def students():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        student_id = request.form.get('student_id')
        course_ids = request.form.getlist('course_ids')  # Note: we use getlist to capture multiple selections
        
        try:
            # Check if student already exists
            existing_student = Student.query.filter_by(student_id=student_id).first()
            if existing_student:
                flash('Student ID already exists!', 'danger')
            else:
                new_student = Student(
                    name=name,
                    student_id=student_id,
                    face_encoding=None
                )
                
                # Add the student to selected courses
                if course_ids:
                    courses = Course.query.filter(Course.id.in_(course_ids)).all()
                    new_student.courses = courses
                
                db.session.add(new_student)
                db.session.commit()
                flash('Student added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding student: {str(e)}")
            flash(f"Database error: {str(e)}", "danger")
    
    try:
        students = Student.query.all()
        courses = Course.query.all()
    except Exception as e:
        logger.error(f"Error retrieving students or courses: {str(e)}")
        students = []
        courses = []
        flash(f"Database error: {str(e)}", "danger")
    
    return render_template('students.html', students=students, courses=courses, error=error)
@app.route('/delete_student/<int:id>', methods=['POST'])
def delete_student(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        student = Student.query.get_or_404(id)
        db.session.delete(student)
        db.session.commit()
        flash('Student deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting student: {str(e)}")
        flash(f"Database error: {str(e)}", "danger")
    
    return redirect(url_for('students'))

@app.route('/courses', methods=['GET', 'POST'])
def courses():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    error = None
    if request.method == 'POST':
        name = request.form.get('name')
        course_id = request.form.get('course_id')
        
        try:
            # Check if course already exists
            existing_course = Course.query.filter_by(course_id=course_id).first()
            if existing_course:
                flash('Course ID already exists!', 'danger')
            else:
                new_course = Course(
                    name=name,
                    course_id=course_id
                )
                db.session.add(new_course)
                db.session.commit()
                flash('Course added successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error adding course: {str(e)}")
            flash(f"Database error: {str(e)}", "danger")
    
    try:
        courses = Course.query.all()
    except Exception as e:
        logger.error(f"Error retrieving courses: {str(e)}")
        courses = []
        flash(f"Database error: {str(e)}", "danger")
    
    students = []  # Only for the template structure
    return render_template('students.html', courses=courses, students=students, active_tab='courses')

@app.route('/face_registration')
def face_registration():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        students = Student.query.all()
    except Exception as e:
        logger.error(f"Error retrieving students for face registration: {str(e)}")
        students = []
        flash(f"Database error: {str(e)}", "danger")
    
    return render_template('face_registration.html', students=students)

@app.route('/register_face', methods=['POST'])
def register_face():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        student_id = request.form.get('student_id')
        image_data = request.form.get('image_data')
        
        if not student_id or not image_data:
            return jsonify({
                "status": "error", 
                "message": "Missing required parameters"
            }), 400
        
        # Find the student
        student = Student.query.get(student_id)
        if not student:
            return jsonify({
                "status": "error", 
                "message": "Student not found"
            }), 404
            
        # Process the image to detect face quality
        image = process_image_data(image_data)
        if image is None:
            return jsonify({
                "status": "error", 
                "message": "Could not process the image. Please try again."
            }), 400
            
        # Detect faces
        faces = detect_face(image)
        
        # Validate face detection
        if len(faces) == 0:
            return jsonify({
                "status": "error", 
                "message": "No face detected in the image. Please ensure your face is clearly visible."
            }), 400
            
        if len(faces) > 1:
            return jsonify({
                "status": "error", 
                "message": "Multiple faces detected. Please ensure only one person is in the frame."
            }), 400
            
        # Check face size - should be large enough for good recognition
        x, y, w, h = faces[0]
        if w < 100 or h < 100:
            return jsonify({
                "status": "error", 
                "message": "Face is too small in the image. Please move closer to the camera."
            }), 400
            
        # Process and encode the face
        face_features = process_and_encode_face(image_data)
        
        if face_features is None:
            return jsonify({
                "status": "error", 
                "message": "Could not extract facial features. Please ensure good lighting and a clear view of your face."
            }), 400
            
        # Convert the features to a JSON string for storage
        face_encoding_json = json.dumps(face_features.tolist())
        
        # Save to the database
        student.face_encoding = face_encoding_json
        db.session.commit()
        
        logger.info(f"Face registered successfully for student {student.id} ({student.name})")
        
        return jsonify({
            "status": "success", 
            "message": f"Face registered successfully for {student.name}"
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in face registration: {str(e)}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500
@app.route('/attendance')
def attendance():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        courses = Course.query.all()
    except Exception as e:
        logger.error(f"Error retrieving courses for attendance: {str(e)}")
        courses = []
        flash(f"Database error: {str(e)}", "danger")
    
    return render_template('attendance.html', courses=courses)

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        course_id = request.form.get('course_id')
        image_data = request.form.get('image_data')
        
        if not course_id or not image_data:
            return jsonify({
                "status": "error", 
                "message": "Missing required parameters"
            }), 400
        
        # Get students enrolled in this course
        course = Course.query.get(course_id)
        if not course:
            return jsonify({
                "status": "error", 
                "message": "Course not found"
            }), 404
        
        # Prepare face encodings and corresponding student IDs
        known_encodings = []
        known_ids = []
        student_names = {}  # For better logging
        
        # Get all students in this course
        students = course.students.all()
        
        # Build the known encodings and IDs
        for student in students:
            if student.face_encoding:
                try:
                    encoding = np.array(json.loads(student.face_encoding))
                    known_encodings.append(encoding)
                    known_ids.append(student.id)
                    student_names[student.id] = student.name
                except Exception as e:
                    logger.warning(f"Could not load face encoding for student {student.id} ({student.name}): {str(e)}")
        
        if not known_encodings:
            return jsonify({
                "status": "error", 
                "message": "No students with registered faces found in this course"
            }), 400
        
        # Use a very high threshold (0.75) for extremely strict face matching
        # This will require faces to be extremely similar to be recognized
        recognized_student_ids = recognize_faces(image_data, known_encodings, known_ids, tolerance=0.75)
        
        # Log which students were recognized for debugging
        if recognized_student_ids:
            logger.info(f"Recognized students: {[student_names.get(id, id) for id in recognized_student_ids]}")
        else:
            logger.info("No students recognized. Face verification failed.")
            
            # Debug log the highest similarity score
            image = process_image_data(image_data)
            if image is not None:
                faces = detect_face(image)
                if len(faces) > 0:
                    face_features = extract_face_features(image, faces[0])
                    if face_features is not None:
                        if np.linalg.norm(face_features) > 0:
                            face_features = face_features / np.linalg.norm(face_features)
                            
                            # Find highest similarity
                            max_similarity = 0
                            max_student_id = None
                            
                            for i, known_encoding in enumerate(known_encodings):
                                if np.linalg.norm(known_encoding) > 0:
                                    known_encoding_norm = known_encoding / np.linalg.norm(known_encoding)
                                else:
                                    known_encoding_norm = known_encoding
                                similarity = np.dot(face_features, known_encoding_norm)
                                
                                if similarity > max_similarity:
                                    max_similarity = similarity
                                    max_student_id = known_ids[i]
                            
                            logger.info(f"Highest similarity: {max_similarity} for student {student_names.get(max_student_id, max_student_id)}")
            
            return jsonify({
                "status": "error", 
                "message": "No students recognized. Face verification failed. Please ensure you are the registered student and try again with better lighting and positioning."
            }), 400
        
        # Mark attendance for recognized students
        marked_students = []
        for student_id in recognized_student_ids:
            # Get the student object
            student = Student.query.get(student_id)
            if not student:
                continue
                
            # Double-check that student is in this course - extra security measure
            course_ids = [c.id for c in student.courses]
            if int(course_id) not in course_ids:
                logger.warning(f"Security alert: Student {student.id} ({student.name}) recognized but not enrolled in course {course_id}")
                continue
            
            # Check if attendance already marked for today
            today = datetime.now().date()
            existing_attendance = Attendance.query.filter(
                Attendance.student_id == student_id,
                Attendance.course_id == course_id,
                db.func.date(Attendance.timestamp) == today
            ).first()
            
            if not existing_attendance:
                new_attendance = Attendance(
                    student_id=student_id,
                    course_id=course_id,
                    timestamp=datetime.now()
                )
                db.session.add(new_attendance)
                marked_students.append(student.name)
        
        db.session.commit()
        
        if marked_students:
            return jsonify({
                "status": "success", 
                "message": f"Attendance marked for: {', '.join(marked_students)}"
            })
        else:
            return jsonify({
                "status": "info", 
                "message": "No new attendances recorded. Students may already be marked present for today."
            })
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in marking attendance: {str(e)}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500
@app.route('/reports')
def reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        courses = Course.query.all()
        students = Student.query.all()
    except Exception as e:
        logger.error(f"Error retrieving data for reports: {str(e)}")
        courses = []
        students = []
        flash(f"Database error: {str(e)}", "danger")
    
    return render_template('reports.html', courses=courses, students=students)

@app.route('/get_attendance_data', methods=['GET'])
def get_attendance_data():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    
    try:
        course_id = request.args.get('course_id')
        student_id = request.args.get('student_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        # Fixed query with explicit join paths
        query = db.session.query(
            Attendance, Student.name.label('student_name'), Course.name.label('course_name')
        ).select_from(Attendance).\
          join(Student, Attendance.student_id == Student.id).\
          join(Course, Attendance.course_id == Course.id)
        
        # Apply filters
        if course_id and course_id != 'all':
            query = query.filter(Attendance.course_id == course_id)
        
        if student_id and student_id != 'all':
            query = query.filter(Attendance.student_id == student_id)
        
        if date_from:
            query = query.filter(Attendance.timestamp >= date_from)
        
        if date_to:
            query = query.filter(Attendance.timestamp <= date_to + " 23:59:59")
        
        # Order by date
        query = query.order_by(Attendance.timestamp.desc())
        
        results = query.all()
        
        # Format the data for the response
        attendance_data = []
        for record in results:
            attendance = record[0]  # The Attendance instance
            student_name = record.student_name
            course_name = record.course_name
            
            attendance_data.append({
                'id': attendance.id,
                'student_name': student_name,
                'course_name': course_name,
                'timestamp': attendance.timestamp.isoformat(),
                'date': attendance.timestamp.strftime('%Y-%m-%d'),
                'time': attendance.timestamp.strftime('%H:%M:%S')
            })
        
        return jsonify({
            "status": "success",
            "data": attendance_data
        })
    
    except Exception as e:
        logger.error(f"Error retrieving attendance data: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"An error occurred: {str(e)}"
        }), 500

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connectivity
        db.session.execute("SELECT 1")
        
        # All checks passed
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "message": "All systems operational"
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "message": f"System error: {str(e)}"
        }), 500

@app.route('/dbinfo')
def db_info():
    """Database information endpoint"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get database version
        version_query = db.session.execute("SELECT version()").fetchone()
        version = version_query[0] if version_query else "Unknown"
        
        # Get table counts
        user_count = User.query.count()
        student_count = Student.query.count()
        course_count = Course.query.count()
        attendance_count = Attendance.query.count()
        
        # Get database connection info (safely)
        connection_info = app.config["SQLALCHEMY_DATABASE_URI"]
        # Mask password for security
        if '@' in connection_info:
            connection_info = connection_info.split('@')
            auth_part = connection_info[0].split(':')
            if len(auth_part) > 2:  # There's a password
                masked_info = f"{auth_part[0]}:***@{connection_info[1]}"
                connection_info = masked_info
            else:
                connection_info = app.config["SQLALCHEMY_DATABASE_URI"]
        
        return jsonify({
            "database_version": version,
            "connection_info": connection_info,
            "table_counts": {
                "users": user_count,
                "students": student_count,
                "courses": course_count,
                "attendance_records": attendance_count
            }
        })
    except Exception as e:
        logger.error(f"Error getting database info: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Database error: {str(e)}"
        }), 500
@app.route('/edit_student/<int:id>', methods=['GET', 'POST'])
def edit_student(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        student = Student.query.get_or_404(id)
        
        if request.method == 'POST':
            # Update student information
            student.name = request.form.get('name')
            
            # Get selected courses
            course_ids = request.form.getlist('course_ids')
            
            # Update courses
            if course_ids:
                courses = Course.query.filter(Course.id.in_(course_ids)).all()
                student.courses = courses
            else:
                student.courses = []
            
            db.session.commit()
            flash('Student updated successfully!', 'success')
            return redirect(url_for('students'))
        
        # Get all courses for the form
        courses = Course.query.all()
        
        # Get the IDs of courses the student is already enrolled in
        enrolled_course_ids = [course.id for course in student.courses]
        
        return render_template('edit_student.html', student=student, courses=courses, enrolled_course_ids=enrolled_course_ids)
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error editing student: {str(e)}")
        flash(f"Error updating student: {str(e)}", "danger")
        return redirect(url_for('students'))
@app.route('/db_admin')
def db_admin():
    """Database admin page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        # Get database version
        version_query = db.session.execute(db.text("SELECT version()")).fetchone()
        db_version = version_query[0] if version_query else "Unknown"
        
        # Get PostgreSQL connection info for displaying
        pg_host = os.environ.get("PGHOST", "localhost")
        pg_port = os.environ.get("PGPORT", "5432")
        pg_user = os.environ.get("PGUSER", "postgres")
        pg_database = os.environ.get("PGDATABASE", "postgres")
        
        # Get table counts
        tables = {
            "Users": User.query.count(),
            "Students": Student.query.count(),
            "Courses": Course.query.count(),
            "Attendance Records": Attendance.query.count()
        }
        
        # Get connection info to display in template
        db_info = {
            'type': 'PostgreSQL',
            'host': pg_host,
            'port': pg_port,
            'user': pg_user,
            'database': pg_database,
            'tables': {
                'users': tables["Users"],
                'students': tables["Students"], 
                'courses': tables["Courses"],
                'attendances': tables["Attendance Records"]
            }
        }
        
        # Schema information
        schema_query = db.session.execute(db.text("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)).fetchall()
        
        # Organize by table
        schema = {}
        for row in schema_query:
            table = row[0]
            if table not in schema:
                schema[table] = []
            schema[table].append({
                "column": row[1],
                "type": row[2],
                "nullable": row[3]
            })
        
        # Index information
        index_query = db.session.execute(db.text("""
            SELECT
                t.relname AS table_name,
                i.relname AS index_name,
                array_to_string(array_agg(a.attname), ', ') AS column_names
            FROM
                pg_class t,
                pg_class i,
                pg_index ix,
                pg_attribute a
            WHERE
                t.oid = ix.indrelid
                AND i.oid = ix.indexrelid
                AND a.attrelid = t.oid
                AND a.attnum = ANY(ix.indkey)
                AND t.relkind = 'r'
                AND t.relname NOT LIKE 'pg_%'
            GROUP BY
                t.relname,
                i.relname
            ORDER BY
                t.relname,
                i.relname;
        """)).fetchall()
        
        indices = {}
        for row in index_query:
            table = row[0]
            if table not in indices:
                indices[table] = []
            indices[table].append({
                "name": row[1],
                "columns": row[2]
            })
        
        # Get connection information
        connection_info = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        # Mask password for security
        if '@' in connection_info:
            connection_info = connection_info.split('@')
            auth_part = connection_info[0].split(':')
            if len(auth_part) > 2:  # There's a password
                masked_info = f"{auth_part[0]}:***@{connection_info[1]}"
                connection_info = masked_info
            
        # Check database connection and constraints
        db_status = "Connected"
        constraints_status = "Valid"
        
        try:
            # Test a quick query
            db.session.execute(db.text("SELECT 1")).fetchone()
            
            # Additional check for foreign key constraints
            # This query checks for FK violations
            fk_check = db.session.execute(db.text("""
                SELECT c.conname AS constraint_name,
                       c.conrelid::regclass AS table_name
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE c.contype = 'f'
                  AND n.nspname = 'public'
                ORDER BY c.conname;
            """)).fetchall()
            
            if not fk_check:
                constraints_status = "Unknown (no foreign keys found)"
                
        except Exception as e:
            db_status = f"Error: {str(e)}"
            constraints_status = "Unknown (couldn't verify)"
            
        # Sample data for pgAdmin instructions
        pgadmin_instructions = [
            f"1. Install pgAdmin from https://www.pgadmin.org/",
            f"2. Launch pgAdmin and click 'Add New Server'",
            f"3. On the General tab, give your connection a name (e.g., 'Attendance System')",
            f"4. On the Connection tab, enter these details:",
            f"   - Host: {pg_host}",
            f"   - Port: {pg_port}",
            f"   - Maintenance Database: {pg_database}",
            f"   - Username: {pg_user}",
            f"5. Click Save to connect"
        ]
        
        # Troubleshooting info
        troubleshooting = {
            "common_errors": [
                {"error": "FATAL: password authentication failed for user", 
                 "solution": "Check that the correct database password is set in the PGPASSWORD environment variable"},
                {"error": "FATAL: role 'username' does not exist", 
                 "solution": "Ensure the user specified in PGUSER exists in PostgreSQL"},
                {"error": "FATAL: database 'dbname' does not exist", 
                 "solution": "Create the database specified in PGDATABASE or update the variable"},
                {"error": "could not connect to server: Connection refused", 
                 "solution": "Verify PostgreSQL is running and accessible at the host/port specified"},
                {"error": "no password supplied", 
                 "solution": "Set the PGPASSWORD environment variable"}
            ],
            "connection_checklist": [
                "PostgreSQL server is running",
                "Database credentials are correct",
                "Network allows connections to the database port",
                "Database exists",
                "User has proper permissions"
            ]
        }
        
        return render_template('db_admin.html', 
                             db_info=db_info, 
                             version=db_version,
                             tables=tables,
                             schema=schema,
                             indices=indices,
                             connection=connection_info,
                             db_status=db_status,
                             constraints=constraints_status,
                             troubleshooting=troubleshooting,
                             pgadmin_instructions=pgadmin_instructions)
    
    except Exception as e:
        logger.error(f"Error in db_admin: {str(e)}")
        flash(f"Database error: {str(e)}", "danger")
        return render_template('db_admin.html', error=str(e))
@app.route('/flow_diagram')
def flow_diagram():
    """System flow diagram page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('flow_diagram.html')

@app.route('/er_diagram')
def er_diagram():
    """Entity relationship diagram page"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('er_diagram.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Handle forgot password requests using security questions - First step"""
    message = None
    error = None
    security_question = None
    
    if request.method == 'POST':
        email = request.form.get('email')
        email_submitted = request.form.get('email_submitted')
        
        if not email:
            error = 'Email is required'
        else:
            # Find user by email
            user = User.query.filter_by(email=email).first()
            
            if not user:
                error = 'No account found with that email address'
            elif not email_submitted:
                # First step - show security question
                if not user.security_question:
                    error = 'This account does not have a security question set up. Please contact support.'
                else:
                    # Show the security question in the form
                    security_question = user.security_question
            else:
                # Second step - verify security answer
                security_answer = request.form.get('security_answer')
                
                if not security_answer:
                    error = 'Security answer is required'
                    security_question = user.security_question
                elif not user.verify_security_answer(security_answer):
                    error = 'Incorrect security answer'
                    security_question = user.security_question
                else:
                    # Store the user's email in the session for the reset page
                    session['reset_email'] = user.email
                    # Set a timestamp to expire the reset session after 15 minutes
                    session['reset_expiry'] = datetime.utcnow().timestamp() + 900  # 15 minutes
                    # Redirect to the reset password page
                    return redirect(url_for('reset_password_direct'))
    
    return render_template('forgot_password.html', message=message, error=error, security_question=security_question)

@app.route('/reset_password_direct', methods=['GET', 'POST'])
def reset_password_direct():
    """Handle direct password reset after security question verification"""
    # Check if reset session is valid
    if 'reset_email' not in session or 'reset_expiry' not in session:
        flash('Password reset session not found. Please try again.', 'danger')
        return redirect(url_for('forgot_password'))
    
    # Check if reset session is expired
    if datetime.utcnow().timestamp() > session.get('reset_expiry', 0):
        # Clear expired session data
        session.pop('reset_email', None)
        session.pop('reset_expiry', None)
        flash('The password reset session has expired. Please try again.', 'warning')
        return redirect(url_for('forgot_password'))
    
    error = None
    if request.method == 'POST':
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not new_password or len(new_password) < 8:
            error = 'New password must be at least 8 characters long'
        elif new_password != confirm_password:
            error = 'Passwords do not match'
        else:
            try:
                # Retrieve user by email stored in session
                user = User.query.filter_by(email=session['reset_email']).first()
                if user:
                    # Update the user's password
                    user.password_hash = generate_password_hash(new_password)
                    db.session.commit()
                    
                    # Clear reset session data
                    session.pop('reset_email', None)
                    session.pop('reset_expiry', None)
                    
                    flash('Your password has been reset successfully! You can now login.', 'success')
                    return redirect(url_for('login'))
                else:
                    error = 'User not found. Please try the reset process again.'
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error resetting password: {str(e)}")
                error = f"Database error: {str(e)}"
    
    return render_template('reset_password.html', error=error)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Legacy route for token-based password reset - redirects to security question based reset"""
    flash('We have updated our password reset system. Please use the security question method below.', 'info')
    return redirect(url_for('forgot_password'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)