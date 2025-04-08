#!/usr/bin/env python3
"""
Database Utilities for Facial Recognition Attendance System
Helps with database migration and maintenance
"""

import os
import json
import logging
from datetime import datetime
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import pymysql

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url(db_type='mysql'):
    """Get database URL based on environment variables and preferences"""
    if db_type == 'mysql':
        mysql_url = os.environ.get("MYSQL_DATABASE_URL")
        if not mysql_url:
            mysql_user = os.environ.get("MYSQL_USER", "root")
            mysql_password = os.environ.get("MYSQL_PASSWORD", "password")
            mysql_host = os.environ.get("MYSQL_HOST", "localhost")
            mysql_port = os.environ.get("MYSQL_PORT", "3306")
            mysql_database = os.environ.get("MYSQL_DATABASE", "attendance_system")
            return f"mysql+pymysql://{mysql_user}:{mysql_password}@{mysql_host}:{mysql_port}/{mysql_database}"
        return mysql_url
    
    elif db_type == 'postgresql':
        pg_url = os.environ.get("DATABASE_URL")
        if pg_url and pg_url.startswith("postgres://"):
            pg_url = pg_url.replace("postgres://", "postgresql://", 1)
        return pg_url
    
    # Fallback to SQLite
    return "sqlite:///attendance.db"

def export_data(source_db_type='postgresql', output_file='db_export.json'):
    """Export data from the source database to a JSON file"""
    try:
        source_url = get_database_url(source_db_type)
        if not source_url:
            logger.error(f"Could not determine {source_db_type} database URL")
            return False
        
        engine = create_engine(source_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Export data table by table
        data = {}
        
        # Users
        users = []
        for row in session.execute(text("SELECT id, username, email, password_hash, created_at FROM users")):
            users.append({
                'id': row[0],
                'username': row[1],
                'email': row[2],
                'password_hash': row[3],
                'created_at': row[4].isoformat() if row[4] else None
            })
        data['users'] = users
        
        # Courses
        courses = []
        for row in session.execute(text("SELECT id, name, course_id, created_at FROM courses")):
            courses.append({
                'id': row[0],
                'name': row[1],
                'course_id': row[2],
                'created_at': row[3].isoformat() if row[3] else None
            })
        data['courses'] = courses
        
        # Students
        students = []
        for row in session.execute(text("SELECT id, name, student_id, course_id, face_encoding, created_at FROM students")):
            students.append({
                'id': row[0],
                'name': row[1],
                'student_id': row[2],
                'course_id': row[3],
                'face_encoding': row[4],
                'created_at': row[5].isoformat() if row[5] else None
            })
        data['students'] = students
        
        # Attendance
        attendance = []
        for row in session.execute(text("SELECT id, student_id, course_id, timestamp FROM attendances")):
            attendance.append({
                'id': row[0],
                'student_id': row[1],
                'course_id': row[2],
                'timestamp': row[3].isoformat() if row[3] else None
            })
        data['attendance'] = attendance
        
        # Write to file
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Data exported successfully to {output_file}")
        return True
    
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return False

def import_data(target_db_type='mysql', input_file='db_export.json'):
    """Import data from a JSON file to the target database"""
    try:
        target_url = get_database_url(target_db_type)
        if not target_url:
            logger.error(f"Could not determine {target_db_type} database URL")
            return False
        
        # Load data from file
        with open(input_file, 'r') as f:
            data = json.load(f)
        
        engine = create_engine(target_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Clear existing data (if any)
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        session.execute(text("TRUNCATE TABLE attendances"))
        session.execute(text("TRUNCATE TABLE students"))
        session.execute(text("TRUNCATE TABLE courses"))
        session.execute(text("TRUNCATE TABLE users"))
        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        session.commit()
        
        # Import users
        for user in data['users']:
            created_at = user['created_at'] if user['created_at'] else datetime.now().isoformat()
            session.execute(
                text("INSERT INTO users (id, username, email, password_hash, created_at) VALUES (:id, :username, :email, :password_hash, :created_at)"),
                {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'password_hash': user['password_hash'],
                    'created_at': created_at
                }
            )
        
        # Import courses
        for course in data['courses']:
            created_at = course['created_at'] if course['created_at'] else datetime.now().isoformat()
            session.execute(
                text("INSERT INTO courses (id, name, course_id, created_at) VALUES (:id, :name, :course_id, :created_at)"),
                {
                    'id': course['id'],
                    'name': course['name'],
                    'course_id': course['course_id'],
                    'created_at': created_at
                }
            )
        
        # Import students
        for student in data['students']:
            created_at = student['created_at'] if student['created_at'] else datetime.now().isoformat()
            session.execute(
                text("INSERT INTO students (id, name, student_id, course_id, face_encoding, created_at) VALUES (:id, :name, :student_id, :course_id, :face_encoding, :created_at)"),
                {
                    'id': student['id'],
                    'name': student['name'],
                    'student_id': student['student_id'],
                    'course_id': student['course_id'],
                    'face_encoding': student['face_encoding'],
                    'created_at': created_at
                }
            )
        
        # Import attendance
        for attend in data['attendance']:
            timestamp = attend['timestamp'] if attend['timestamp'] else datetime.now().isoformat()
            session.execute(
                text("INSERT INTO attendances (id, student_id, course_id, timestamp) VALUES (:id, :student_id, :course_id, :timestamp)"),
                {
                    'id': attend['id'],
                    'student_id': attend['student_id'],
                    'course_id': attend['course_id'],
                    'timestamp': timestamp
                }
            )
        
        session.commit()
        logger.info("Data imported successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error importing data: {str(e)}")
        return False

def migrate_postgresql_to_mysql():
    """Migrate data from PostgreSQL to MySQL"""
    try:
        # Export from PostgreSQL
        if not export_data(source_db_type='postgresql', output_file='pg_export.json'):
            return False
        
        # Import to MySQL
        return import_data(target_db_type='mysql', input_file='pg_export.json')
    
    except Exception as e:
        logger.error(f"Error in migration: {str(e)}")
        return False

def migrate_mysql_to_postgresql():
    """Migrate data from MySQL to PostgreSQL"""
    try:
        # Export from MySQL
        if not export_data(source_db_type='mysql', output_file='mysql_export.json'):
            return False
        
        # Import to PostgreSQL
        return import_data(target_db_type='postgresql', input_file='mysql_export.json')
    
    except Exception as e:
        logger.error(f"Error in migration: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Database utilities for attendance system')
    parser.add_argument('--export', choices=['postgresql', 'mysql'], help='Export data from the specified database')
    parser.add_argument('--import', dest='import_db', choices=['postgresql', 'mysql'], help='Import data to the specified database')
    parser.add_argument('--file', default='db_export.json', help='File path for import/export operations')
    parser.add_argument('--migrate', choices=['pg2mysql', 'mysql2pg'], help='Migrate data between databases')
    
    args = parser.parse_args()
    
    if args.export:
        export_data(source_db_type=args.export, output_file=args.file)
    
    elif args.import_db:
        import_data(target_db_type=args.import_db, input_file=args.file)
    
    elif args.migrate:
        if args.migrate == 'pg2mysql':
            migrate_postgresql_to_mysql()
        elif args.migrate == 'mysql2pg':
            migrate_mysql_to_postgresql()
    
    else:
        parser.print_help()