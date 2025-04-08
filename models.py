from app import db
from datetime import datetime, timedelta
from flask_login import UserMixin
import secrets

# Add this association table for many-to-many relationship
student_course_association = db.Table('student_course_association',
    db.Column('student_id', db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), primary_key=True)
)

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    security_question = db.Column(db.String(200), nullable=True)
    security_answer = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def generate_reset_token(self):
        # Generate a secure random token
        self.reset_token = secrets.token_urlsafe(32)
        # Set expiry to 24 hours from now
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=24)
        return self.reset_token
    
    def verify_reset_token(self, token):
        # Check if token matches and is not expired
        if self.reset_token != token:
            return False
        if self.reset_token_expiry is None or self.reset_token_expiry < datetime.utcnow():
            # Token expired
            return False
        return True
    
    def clear_reset_token(self):
        # Clear the token after successful reset
        self.reset_token = None
        self.reset_token_expiry = None
        
    def verify_security_answer(self, answer):
        # Check if the provided answer matches the stored answer (case-insensitive)
        if not self.security_answer or not answer:
            return False
        return self.security_answer.lower() == answer.lower().strip()

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    face_encoding = db.Column(db.Text, nullable=True)  # JSON serialized face encoding
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Update the relationship to use many-to-many
    courses = db.relationship('Course', secondary=student_course_association, 
                            backref=db.backref('students', lazy='dynamic'))
    attendances = db.relationship('Attendance', backref='student', lazy=True, cascade="all, delete-orphan")

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    attendances = db.relationship('Attendance', backref='course', lazy=True, cascade="all, delete-orphan")

class Attendance(db.Model):
    __tablename__ = 'attendances'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Add index for faster reporting queries
    __table_args__ = (
        db.Index('idx_attendance_date', timestamp),
        db.Index('idx_student_course', student_id, course_id),
    )