from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import json
import os
import openai

app = Flask(__name__)
app.secret_key = 'visionboardai-secret-key-2024'  # Change this in production

# OpenAI API Configuration
openai.api_key = os.getenv('OPENAI_API_KEY')
if not openai.api_key:
    print("Warning: OPENAI_API_KEY1 environment variable not set. AI features will be disabled.")

# Jinja2 Filters and Context Processors
@app.template_filter('format_date')
def format_date(date_string):
    """Format date string to readable format"""
    if not date_string:
        return ''
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date_obj.strftime('%B %d, %Y')
    except:
        return date_string

@app.template_filter('time_ago')
def time_ago(date_string):
    """Return time ago from date string"""
    if not date_string:
        return ''
    try:
        date_obj = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        now = datetime.now()
        diff = now - date_obj
        days = diff.days
        if days == 0:
            return 'Today'
        elif days == 1:
            return 'Yesterday'
        elif days < 7:
            return f'{days} days ago'
        elif days < 30:
            weeks = days // 7
            return f'{weeks} week{"s" if weeks > 1 else ""} ago'
        else:
            months = days // 30
            return f'{months} month{"s" if months > 1 else ""} ago'
    except:
        return date_string

@app.context_processor
def inject_utilities():
    """Inject utility functions into template context"""
    return {
        'get_priority_color': lambda priority: {
            'high': 'priority-high',
            'medium': 'priority-medium',
            'low': 'priority-low'
        }.get(priority, 'priority-medium'),
        'get_category_icon': lambda category: {
            'career': 'fas fa-briefcase',
            'health': 'fas fa-heartbeat',
            'education': 'fas fa-graduation-cap',
            'finance': 'fas fa-dollar-sign',
            'relationships': 'fas fa-users',
            'personal': 'fas fa-user',
            'hobby': 'fas fa-palette'
        }.get(category, 'fas fa-bullseye')
    }

# Ensure data directory exists
if not os.path.exists('data'):
    os.makedirs('data')

# File to store goals
GOALS_FILE = 'data/goals.json'

def load_goals():
    """Load goals from JSON file"""
    if os.path.exists(GOALS_FILE):
        with open(GOALS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_goals(goals):
    """Save goals to JSON file"""
    with open(GOALS_FILE, 'w') as f:
        json.dump(goals, f, indent=2)

def is_openai_available():
    """Check if OpenAI API is available"""
    return bool(openai.api_key)

def generate_weekly_tasks(goal):
    """Generate weekly tasks for a goal using OpenAI API"""
    if not is_openai_available():
        return []
    
    try:
        prompt = f"""
        Break down this long-term goal into 4-6 actionable weekly tasks:
        
        Goal: {goal['title']}
        Description: {goal['description']}
        Category: {goal['category']}
        Deadline: {goal['deadline']}
        Priority: {goal['priority']}
        
        Please provide weekly tasks that are:
        1. Specific and measurable
        2. Realistic and achievable within a week
        3. Progressive (each week builds on the previous)
        4. Include estimated time commitment
        
        Format each task as: "Week X: [Task description] (estimated time: X hours)"
        """
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant that breaks down long-term goals into actionable weekly tasks."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7
        )
        
        # Parse the response and extract tasks
        content = response.choices[0].message.content
        tasks = []
        
        # Simple parsing - look for lines that start with "Week"
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('Week') and ':' in line:
                task_text = line.split(':', 1)[1].strip()
                tasks.append({
                    'id': len(tasks) + 1,
                    'description': task_text,
                    'week': len(tasks) + 1,
                    'completed': False,
                    'created_at': datetime.now().isoformat()
                })
        
        return tasks[:6]  # Limit to 6 tasks
        
    except Exception as e:
        print(f"Error generating weekly tasks: {e}")
        return []

@app.route("/")
def index():
    """Home page"""
    goals = load_goals()
    return render_template('goals.html', goals=goals)

@app.route("/goals/add", methods=['GET', 'POST'])
def add_goal():
    """Add a new goal"""
    if request.method == 'POST':
        goal_data = {
            'id': datetime.now().strftime('%Y%m%d%H%M%S'),
            'title': request.form.get('title', '').strip(),
            'description': request.form.get('description', '').strip(),
            'category': request.form.get('category', ''),
            'deadline': request.form.get('deadline', ''),
            'priority': request.form.get('priority', 'medium'),
            'status': 'active',
            'created_at': datetime.now().isoformat(),
            'weekly_tasks': []
        }
        
        # Validate required fields
        if not goal_data['title']:
            flash('Goal title is required!', 'error')
            return render_template('goals.html', goal=goal_data)
        
        # Load existing goals and add new one
        goals = load_goals()
        goals.append(goal_data)
        save_goals(goals)
        
        flash('Goal added successfully!', 'success')
        return redirect(url_for('index'))
    
    return render_template('goals.html')

@app.route("/goals/<goal_id>")
def view_goal(goal_id):
    """View a specific goal"""
    goals = load_goals()
    goal = next((g for g in goals if g['id'] == goal_id), None)
    
    if not goal:
        flash('Goal not found!', 'error')
        return redirect(url_for('index'))
    
    return render_template('goals.html', goal=goal, goals=goals)

@app.route("/goals/<goal_id>/edit", methods=['GET', 'POST'])
def edit_goal(goal_id):
    """Edit a goal"""
    goals = load_goals()
    goal = next((g for g in goals if g['id'] == goal_id), None)
    
    if not goal:
        flash('Goal not found!', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        goal['title'] = request.form.get('title', '').strip()
        goal['description'] = request.form.get('description', '').strip()
        goal['category'] = request.form.get('category', '')
        goal['deadline'] = request.form.get('deadline', '')
        goal['priority'] = request.form.get('priority', 'medium')
        
        if not goal['title']:
            flash('Goal title is required!', 'error')
            return render_template('goals.html', goal=goal, goals=goals, editing=True)
        
        save_goals(goals)
        flash('Goal updated successfully!', 'success')
        return redirect(url_for('view_goal', goal_id=goal_id))
    
    return render_template('goals.html', goal=goal, goals=goals, editing=True)

@app.route("/goals/<goal_id>/delete", methods=['POST'])
def delete_goal(goal_id):
    """Delete a goal"""
    goals = load_goals()
    goals = [g for g in goals if g['id'] != goal_id]
    save_goals(goals)
    flash('Goal deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route("/goals/<goal_id>/generate-tasks", methods=['POST'])
def generate_tasks(goal_id):
    """Generate weekly tasks for a goal using AI"""
    goals = load_goals()
    goal = next((g for g in goals if g['id'] == goal_id), None)
    
    if not goal:
        flash('Goal not found!', 'error')
        return redirect(url_for('index'))
    
    if not is_openai_available():
        flash('OpenAI API is not configured. Please set OPENAI_API_KEY1 environment variable.', 'error')
        return redirect(url_for('view_goal', goal_id=goal_id))
    
    try:
        # Generate weekly tasks using AI
        weekly_tasks = generate_weekly_tasks(goal)
        
        if weekly_tasks:
            # Update the goal with generated tasks
            goal['weekly_tasks'] = weekly_tasks
            save_goals(goals)
            flash(f'Generated {len(weekly_tasks)} weekly tasks for your goal!', 'success')
        else:
            flash('Unable to generate weekly tasks. Please try again.', 'error')
            
    except Exception as e:
        flash(f'Error generating tasks: {str(e)}', 'error')
    
    return redirect(url_for('view_goal', goal_id=goal_id))

@app.route("/goals/<goal_id>/tasks/<task_id>/toggle", methods=['POST'])
def toggle_task(goal_id, task_id):
    """Toggle task completion status"""
    goals = load_goals()
    goal = next((g for g in goals if g['id'] == goal_id), None)
    
    if not goal:
        return jsonify({'error': 'Goal not found'}), 404
    
    task = next((t for t in goal['weekly_tasks'] if t['id'] == int(task_id)), None)
    
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    # Toggle completion status
    task['completed'] = not task['completed']
    save_goals(goals)
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'completed': task['completed']
    })

if __name__ == '__main__':
    app.run(debug=True, port=5001)
