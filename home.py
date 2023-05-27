from flask import Flask, request, jsonify
from datetime import datetime,timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import mysql.connector
from flask_limiter import Limiter
from flask_caching import Cache
from dotenv import load_dotenv
import os
load_dotenv()

app = Flask(__name__)

db = mysql.connector.connect(
    host=os.getenv('host'),
    user=os.getenv('user'),
    password=os.getenv('password'),
    database=os.getenv('database')
)
limiter = Limiter(app)
cache = Cache(app)
next_quiz_id = 1
quizzess = []
scheduler = BackgroundScheduler()
scheduler.start()

def update_quiz_status():
    current_time = datetime.now()
    for quiz in quizzess:
        if quiz['start_date'] <= current_time <= quiz['end_date']:
            quiz['updates'] = 'active'
        elif current_time > quiz['end_date']:
            quiz['updates'] = 'finished'
        else:
            quiz['updates'] = 'inactive'


@app.route('/quizzes', methods=['POST'])
@limiter.limit("10/minute")
def create_quiz():
    global next_quiz_id
    # Get the data from the request
    data = request.json

    # Extract the fields from the data
    question = data['question']
    choices = data['choices']
    right_answer = data['rightAnswer']
    start_date = datetime.strptime(data['startDate'], '%Y-%m-%d %H:%M:%S')
    end_date = datetime.strptime(data['endDate'], '%Y-%m-%d %H:%M:%S')

    if datetime.now() > start_date and datetime.now() < end_date :
        update = 'active'
    elif datetime.now() > end_date:
        update = 'finished'
    else:
        update = 'inactive'

    # Create a new quiz dictionary
    quiz = {
        'id': next_quiz_id,
        'question': question,
        'choices': choices,
        'right_answer': right_answer,
        'start_date': start_date,
        'end_date': end_date,
        'updates': update
    }
    print
    # Add the quiz to the list
    quizzess.append(quiz)
    next_quiz_id += 1
    # Store the quiz in the MySQL database
    cursor = db.cursor()
    sql = "INSERT INTO quizzess (question, choices, right_answer, start_date, end_date, updates) VALUES (%s, %s, %s, %s, %s, %s)"
    values = (question, ','.join(choices), right_answer, start_date, end_date, quiz['updates'])
    cursor.execute(sql, values)
    db.commit()

    # Return a success response
    return jsonify({'message': 'Quiz created successfully'})


@app.route('/quizzes/active', methods=['GET'])
@limiter.limit("100/day")  # Limit to 100 requests per day
@cache.cached(timeout=60)
def get_active_quiz():
    current_time = datetime.now()

    for quiz in quizzess:
        if quiz['start_date'] <= current_time <= quiz['end_date']:
            return jsonify(quiz)

    return jsonify({'message': 'No active quiz found'})

@app.route('/quizzes/<int:quiz_id>/result', methods=['GET'])
@limiter.limit("100/day")  # Limit to 100 requests per day
@cache.cached(timeout=60)
def get_quiz_result(quiz_id):
    quiz = next((quiz for quiz in quizzess if quiz['id'] == quiz_id), None)
    print(quiz)
    if not quiz:
        return jsonify({'error': 'Quiz not found'})

    current_time = datetime.now()
    end_time_plus_5_minutes = quiz['end_date'] + timedelta(minutes=5)

    if current_time < end_time_plus_5_minutes:
        return jsonify({'error': 'Quiz result not available yet'})

    return jsonify({'result': quiz['right_answer']})


@app.route('/quizzes/all', methods=['GET'])
@limiter.limit("100/day")  # Limit to 100 requests per day
@cache.cached(timeout=60)
def get_all_quizzess():
    return jsonify(quizzess)




if __name__ == '__main__':
    scheduler.add_job(update_quiz_status, 'interval', minutes=1)
    app.run()