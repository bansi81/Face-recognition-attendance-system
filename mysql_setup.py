#!/usr/bin/env python3
"""
MySQL Database Setup Script for Facial Recognition Attendance System
This script creates the MySQL database and required tables for the application
"""

import os
import pymysql
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_mysql_database():
    """Create the MySQL database and tables"""
    
    # Get MySQL connection parameters from environment variables
    mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
    mysql_port = int(os.environ.get('MYSQL_PORT', 3306))
    mysql_user = os.environ.get('MYSQL_USER', 'root')
    mysql_password = os.environ.get('MYSQL_PASSWORD', 'password')
    mysql_database = os.environ.get('MYSQL_DATABASE', 'attendance_system')
    
    try:
        # First connect without specifying a database to create it if needed
        conn = pymysql.connect(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password,
            charset='utf8mb4'
        )
        
        logger.info(f"Connected to MySQL server at {mysql_host}:{mysql_port}")
        
        with conn.cursor() as cursor:
            # Create database if it doesn't exist
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{mysql_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info(f"Database '{mysql_database}' created or already exists")
            
            # Use the database
            cursor.execute(f"USE `{mysql_database}`")
            
        conn.commit()
        logger.info("Database setup completed successfully")
        
        return True
    
    except Exception as e:
        logger.error(f"Error setting up MySQL database: {str(e)}")
        return False

def check_mysql_connection():
    """Check if MySQL connection parameters are valid"""
    
    mysql_host = os.environ.get('MYSQL_HOST', 'localhost')
    mysql_port = int(os.environ.get('MYSQL_PORT', 3306))
    mysql_user = os.environ.get('MYSQL_USER')
    mysql_password = os.environ.get('MYSQL_PASSWORD')
    
    if not mysql_user or not mysql_password:
        logger.error("MySQL user or password not provided in environment variables")
        return False
    
    try:
        conn = pymysql.connect(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password,
            charset='utf8mb4',
            connect_timeout=5
        )
        conn.close()
        logger.info("MySQL connection successful")
        return True
    
    except Exception as e:
        logger.error(f"MySQL connection failed: {str(e)}")
        return False

def print_mysql_instructions():
    """Print instructions for setting up MySQL"""
    
    print("""
MySQL Connection Setup Instructions
----------------------------------

To use MySQL with this application, you need to provide the following environment variables:

1. MYSQL_HOST - MySQL server hostname (default: localhost)
2. MYSQL_PORT - MySQL server port (default: 3306)
3. MYSQL_USER - MySQL username with database creation privileges
4. MYSQL_PASSWORD - MySQL password for the user
5. MYSQL_DATABASE - Name of the database to use (default: attendance_system)

You can also set DATABASE_TYPE=mysql in your environment to prioritize MySQL over PostgreSQL.

Example setup commands:
    
    # Set environment variables
    export MYSQL_HOST=localhost
    export MYSQL_PORT=3306
    export MYSQL_USER=your_username
    export MYSQL_PASSWORD=your_password
    export MYSQL_DATABASE=attendance_system
    export DATABASE_TYPE=mysql
    
    # Run this setup script
    python mysql_setup.py
    
    # Start the application
    python main.py
""")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print_mysql_instructions()
        sys.exit(0)
    
    if check_mysql_connection():
        success = create_mysql_database()
        if success:
            print("MySQL database setup completed successfully!")
        else:
            print("Failed to set up MySQL database. Check the logs for details.")
    else:
        print("Failed to connect to MySQL. Please check your connection parameters.")
        print_mysql_instructions()