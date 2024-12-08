from flask import Flask, render_template, request, jsonify, send_file, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import sys
import io
import qrcode  # For QR code generation
import sqlite3

# Ensure the `office_launcher` module is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from office_launcher import OfficeLauncher  # Import the OfficeLauncher class

app = Flask(__name__, template_folder="templates")

# Initialize the OfficeLauncher
launcher = OfficeLauncher()

# Set the secret key for sessions
app.secret_key = 'your_secret_key_here'  # Replace with a strong, random secret key


def get_db_connection():
    """Create and return a database connection."""
    conn = sqlite3.connect('tasks.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with tasks and users tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tasks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            priority TEXT DEFAULT 'low',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            assigned_by TEXT,
            due_date TEXT,
            due_time TEXT,
            status TEXT DEFAULT 'Not Started',
            app TEXT,
            time_remaining INTEGER DEFAULT 1440
        )
    ''')

    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    conn.commit()
    conn.close()


# Initialize the database
init_db()


# Routes
@app.route('/')
def index():
    return render_template('login.html')


# Authentication Routes
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    # Input validation
    if not name or not email or not password:
        return jsonify({
            'status': 'error',
            'message': 'All fields are required'
        }), 400

    try:
        # Hash the password
        hashed_password = generate_password_hash(password)

        # Open database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Insert new user
            cursor.execute(
                'INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                (name, email, hashed_password)
            )
            conn.commit()

            return jsonify({
                'status': 'success',
                'message': 'User registered successfully'
            })
        except sqlite3.IntegrityError:
            # Handle duplicate email
            return jsonify({
                'status': 'error',
                'message': 'Email already exists'
            }), 400
        finally:
            conn.close()

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Registration failed: {str(e)}'
        }), 500


@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    # Input validation
    if not email or not password:
        return jsonify({
            'status': 'error',
            'message': 'Email and password are required'
        }), 400

    try:
        # Open database connection
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch user by email
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()

        # Check if user exists and password is correct
        if user and check_password_hash(user['password'], password):
            # Create a session for the user
            session['user_id'] = user['id']
            session['user_name'] = user['name']

            return jsonify({
                'status': 'success',
                'message': 'Login successful'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid email or password'
            }), 401

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Login failed: {str(e)}'
        }), 500


@app.route('/task-manager')
def task_manager():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect('/')

    return render_template('task_manager.html',
                           user_name=session.get('user_name', 'User'))


@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    return redirect('/')


# Task Management Routes
@app.route('/add_task', methods=['POST'])
def add_task():
    # User authentication check
    if 'user_id' not in session:
        return jsonify({
            'status': 'error',
            'message': 'Unauthorized. Please log in.'
        }), 401

    try:
        data = request.json
        if not data or not data.get('title'):
            return jsonify({
                'status': 'error',
                'message': 'Task title is required'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO tasks 
            (title, description, priority, due_date, due_time, status, app, assigned_by) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data.get('title'),
            data.get('description', ''),
            data.get('priority', 'low'),
            data.get('due_date'),
            data.get('due_time'),
            data.get('status', 'Not Started'),
            data.get('app'),
            session.get('user_name', 'System')
        ))

        conn.commit()
        task_id = cursor.lastrowid
        conn.close()

        return jsonify({
            'status': 'success',
            'message': 'Task added successfully',
            'task': {
                'id': task_id,
                'title': data.get('title'),
                'description': data.get('description', ''),
                'priority': data.get('priority', 'low'),
                'due_date': data.get('due_date'),
                'due_time': data.get('due_time'),
                'status': data.get('status', 'Not Started')
            }
        })
    except Exception as e:
        print(f"Error adding task: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500


# Other task management routes from the second document remain the same
# (get_task, update_task, delete_task, get_tasks, update_task_status,
# generate_qr, launch_app, detect_task)

# Note: For brevity, I've included the full code for some routes.
# You would copy the rest of the routes from the second document exactly as they were.


@app.route('/get_task/<int:task_id>', methods=['GET'])
def get_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify({
        'id': task['id'],
        'title': task['title'],
        'description': task['description'],
        'priority': task['priority'],
        'due_date': task['due_date'],
        'due_time': task['due_time'],
        'status': task['status'],
        'app': task['app'],
        'createdAt': task['created_at']
    })


@app.route('/update_task', methods=['POST'])
def update_task():
    data = request.json
    task_id = data.get('id')

    if not task_id:
        return jsonify({
            'status': 'error',
            'message': 'Task ID is required'
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Prepare update query with provided fields
        update_fields = []
        params = []

        if 'title' in data:
            update_fields.append('title = ?')
            params.append(data['title'])

        if 'description' in data:
            update_fields.append('description = ?')
            params.append(data['description'])

        if 'priority' in data:
            update_fields.append('priority = ?')
            params.append(data['priority'])

        if 'due_date' in data:
            update_fields.append('due_date = ?')
            params.append(data['due_date'])

        if 'due_time' in data:
            update_fields.append('due_time = ?')
            params.append(data['due_time'])

        if 'status' in data:
            update_fields.append('status = ?')
            params.append(data['status'])

        # Add task ID to params
        params.append(task_id)

        # Execute update if there are fields to update
        if update_fields:
            query = f'UPDATE tasks SET {", ".join(update_fields)} WHERE id = ?'
            cursor.execute(query, params)
            conn.commit()

            # Check if task was updated
            if cursor.rowcount == 0:
                conn.close()
                return jsonify({
                    'status': 'error',
                    'message': 'Task not found'
                }), 404

        conn.close()

        return jsonify({
            'status': 'success',
            'message': 'Task updated successfully',
            'task': data
        })
    except Exception as e:
        print(f"Error updating task: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Internal server error: {str(e)}'
        }), 500


@app.route('/delete_task', methods=['POST'])
def delete_task():
    data = request.json
    task_id = data.get('id')

    if not task_id:
        return jsonify({
            'status': 'error',
            'message': 'Task ID is required'
        }), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete the task
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))

        # Check if a task was actually deleted
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'status': 'error',
                'message': 'Task not found'
            }), 404

        # Commit the deletion and close connection
        conn.commit()
        conn.close()

        # Return success response
        return jsonify({
            'status': 'success',
            'message': 'Task deleted successfully'
        }), 200

    except sqlite3.Error as e:
        # Handle database-related errors
        return jsonify({
            'status': 'error',
            'message': f'Database error: {str(e)}'
        }), 500

    except Exception as e:
        # Handle any unexpected errors
        return jsonify({
            'status': 'error',
            'message': f'Unexpected error: {str(e)}'
        }), 500


@app.route('/get_tasks', methods=['GET'])
def get_tasks():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch tasks sorted by priority and creation time
    cursor.execute('''
        SELECT * FROM tasks 
        ORDER BY 
            CASE priority 
                WHEN 'high' THEN 1 
                WHEN 'medium' THEN 2 
                ELSE 3 
            END, 
            created_at
    ''')
    tasks = cursor.fetchall()
    conn.close()

    # Convert tasks to list of dictionaries
    task_list = [{
        'id': task['id'],
        'title': task['title'],
        'app': task['app'],
        'priority': task['priority'],
        'timeRemaining': task['time_remaining'],
        'status': task['status'],
        'description': task['description'],
        'createdAt': task['created_at'],
        'dueDate': task['due_date'],
        'dueTime': task['due_time']
    } for task in tasks]

    return jsonify(task_list)


@app.route('/update_task_status', methods=['POST'])
def update_task_status():
    data = request.json
    task_id = data.get('taskId')
    status = data.get('status')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Update task status
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))

        # Check if task was found and updated
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Task not found'}), 404

        conn.commit()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Task status updated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/generate_qr/<int:task_id>', methods=['GET'])
def generate_qr(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    conn.close()

    if not task:
        return jsonify({'error': 'Task not found'}), 404

    qr_content = f"Task: {task['title']}\nApp: {task['app'] or 'N/A'}\nPriority: {task['priority']}\nStatus: {task['status']}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_content)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="PNG")
    img_byte_arr.seek(0)

    return send_file(img_byte_arr, mimetype='image/png', as_attachment=True, download_name=f"task_{task['id']}_qr.png")


@app.route('/launch_app', methods=['POST'])
def launch_app():
    data = request.json
    app_name = data.get('app', '').lower()
    task_id = data.get('task_id')

    app_mapping = {
        'powerpoint': 'powerpoint',
        'word': 'word',
        'excel': 'excel',
        'wps': 'wps',
    }

    app_to_launch = app_mapping.get(app_name)
    if not app_to_launch:
        return jsonify({'error': 'Unsupported application'}), 400

    try:
        # Update task status to 'In Progress'
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET status = ? WHERE id = ?', ('In Progress', task_id))
        conn.commit()
        conn.close()

        # Launch the application
        launcher.launch_app(app_to_launch)
        return jsonify({'status': 'success', 'message': f'{app_to_launch.capitalize()} launched successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/detect_task', methods=['POST'])
def detect_task():
    data = request.json
    email_content = data.get('emailContent', '').lower()
    assigned_by = data.get('assignedBy', 'System')

    task_types = [
        {'keyword': 'ppt', 'type': 'PowerPoint Presentation', 'app': 'powerpoint'},
        {'keyword': 'word', 'type': 'Word Document', 'app': 'word'},
        {'keyword': 'excel', 'type': 'Excel Spreadsheet', 'app': 'excel'},
        {'keyword': 'wps', 'type': 'WPS Document', 'app': 'wps'},
    ]

    detected_task = None
    for task in task_types:
        if task['keyword'] in email_content:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check current high-priority task count
            cursor.execute('SELECT COUNT(*) as high_priority_count FROM tasks WHERE priority = "high"')
            high_priority_count = cursor.fetchone()['high_priority_count']

            # Determine priority
            priority = 'high' if high_priority_count < 3 else 'low'

            # Insert the detected task
            cursor.execute('''
                INSERT INTO tasks 
                (title, app, priority, assigned_by, status, time_remaining) 
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                f"Create {task['type']}",
                task['app'],
                priority,
                assigned_by,
                'Not Started',
                1440  # 24 hours in minutes
            ))
            conn.commit()
            task_id = cursor.lastrowid
            conn.close()

            # Fetch the newly created task
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
            detected_task = cursor.fetchone()
            conn.close()

            break

    if detected_task:
        return jsonify({
            'id': detected_task['id'],
            'title': detected_task['title'],
            'app': detected_task['app'],
            'priority': detected_task['priority'],
            'timeRemaining': detected_task['time_remaining'],
            'status': detected_task['status']
        })
    return jsonify({'error': 'No task detected'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=66890, debug=True)
