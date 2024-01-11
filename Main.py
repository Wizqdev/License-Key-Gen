from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_basicauth import BasicAuth
import random
import string
import datetime
from pymongo import MongoClient
import json

# Load configuration from config.json
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

app = Flask(__name__, template_folder='View')
app.secret_key = config['Web']['Secret']

basic_auth = BasicAuth(app)

mongodb_uri = config['Database']['MongoDB']
port = config['Web']['Port']
admin_username = config['Admin']['Username']
admin_password = config['Admin']['Password']

client = MongoClient(mongodb_uri)
db = client['LICENSEKEY']
license_collection = db['license_keys']

def generate_license_key(length=12):
    key = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return key

def parse_validity(request):
    days = int(request.form.get('days', 0)) if request.form.get('days') else 0
    hours = int(request.form.get('hours', 0)) if request.form.get('hours') else 0
    minutes = int(request.form.get('minutes', 0)) if request.form.get('minutes') else 0
    seconds = int(request.form.get('seconds', 0)) if request.form.get('seconds') else 0
    return datetime.timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)

def delete_expired_keys():
    current_time = datetime.datetime.now()
    license_collection.delete_many({"expiration_date": {"$lt": current_time}})

@basic_auth.required
def is_admin():
    return request.authorization.username == admin_username and \
           request.authorization.password == admin_password

def is_authenticated():
    return 'logged_in' in session and session['logged_in']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == admin_username and password == admin_password:
            session['logged_in'] = True
            return redirect(url_for('dashboardindex'))
        else:
            return render_template('login.html', error='Invalid credentials')
    return render_template('login.html', error=None)

@app.route('/dashboard')
def dashboardindex():
    if not is_authenticated():
        return redirect(url_for('login'))
    delete_expired_keys()

    license_keys = license_collection.find()
    return render_template('dashboard/index.html', license_keys=license_keys)

@app.route('/create_license', methods=['POST'])
def create_license():
    user = request.form['user']
    validity = parse_validity(request)
    expiration_date = datetime.datetime.now() + validity
    license_key = generate_license_key()
    license_collection.insert_one({"key": license_key, "user": user, "expiration_date": expiration_date})
    return redirect(url_for('dashboardindex'))

@app.route('/delete_license/<license_key>')
def delete_license(license_key):
    license_collection.delete_one({"key": license_key})
    return redirect(url_for('index'))

@app.route('/validate_license', methods=['POST'])
def validate_license():
    user_license_key = request.form['license_key']

    delete_expired_keys()

    license = license_collection.find_one({"key": user_license_key, "expiration_date": {"$gte": datetime.datetime.now()}})

    if license:
        return jsonify({
            "valid": True,
            "message": "License key is valid!",
            "user": license["user"],
            "valid_date": license["expiration_date"].strftime("%Y-%m-%d %H:%M:%S")
        })
    else:
        return jsonify({"valid": False, "error": "License key not found or not valid!"})

if __name__ == '__main__':
    app.run(debug=False, port=port)
    