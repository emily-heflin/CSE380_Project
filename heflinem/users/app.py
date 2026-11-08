#USER SERVICE	

import sqlite3
import os
import json
from flask import Flask, request, Response
import hashlib
import hmac
import base64
import requests


app = Flask(__name__)
db_name = "user.db"
sql_file = "user.sql"
db_flag = False

# PASSWORD CHECKS 
# Returns True if the password contains at least one lowercase letter
def is_lower(p):
    for char in p:
        if char.islower():
            return True
    return False
# Returns True if the password contains at least one uppercase letter
def is_upper(p):
    for char in p:
        if char.isupper():
            return True
    return False
# Returns True if the password contains at least one digit
def is_digit(p):
    for char in p:
        if char.isdigit():
            return True
    return False
# Checks if the password meets the requirements
def check_pass(password, username, first_name, last_name):
    check = True
    if (len(password) < 8):
        check = False
    elif (not is_lower(password)):
        check = False
    elif (not is_upper(password)):
        check = False
    elif ((password.lower()).find(username.lower()) != -1):
        check = False
    elif ((password.lower()).find(first_name.lower()) != -1):
        check = False
    elif ((password.lower()).find(last_name.lower()) != -1):
        check = False
    elif (not is_digit(password)):
        check = False
    return check
# Checks if the username is already taken
def check_user(username):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
    result = cursor.fetchone() is None
    conn.close()
    return result
# Checks if the email is already taken
def check_email(email_address):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email_address = ?;", (email_address,))
    result = cursor.fetchone() is None
    conn.close()
    return result
# Checks if the JWT is valid user

'''
def load_key():
    base_dir = os.path.dirname(os.path.abspath(__file__))  # folder where this service lives
    key_path = os.path.join(base_dir, "..", "key.txt")     # move up one directory

    with open(key_path, "r") as f:
        return f.read().strip()
'''

def check_jwt(jwt):
    try:
        header_b64, payload_b64, signature_hex = jwt.split('.')
        signing_input = f"{header_b64}.{payload_b64}".encode()

        #secret_key = load_key()
        with open("key.txt") as f:
            secret_key = f.read().strip()
            expected_signature = hmac.new(
            secret_key.encode(),
            signing_input,
            hashlib.sha256
        ).digest()
        return hmac.compare_digest(expected_signature.hex(), signature_hex)
    except Exception:
        return False

# Gets the username from the JWT
def get_user(jwt):
    header_b64, payload_b64, signature_hex = jwt.split('.')
    payload_json = base64.urlsafe_b64decode(payload_b64 + '==').decode()
    payload = json.loads(payload_json)
    return payload['username']

def create_db():
    conn = sqlite3.connect(db_name)
    
    with open(sql_file, 'r') as sql_startup:
        init_db = sql_startup.read()
    cursor = conn.cursor()
    cursor.executescript(init_db)
    conn.commit()
    conn.close()
    global db_flag
    db_flag = True
    #return conn
'''
def get_db():
    global conn_global, db_flag
    if conn_global is None:
        if not db_flag:
            create_db()
            db_flag = True
        conn_global = sqlite3.connect(db_name)
    return conn_global
'''

def get_db():
    if not db_flag:
        create_db()
    conn = sqlite3.connect(db_name)
    return conn

def dollars_to_cents(amount_str):
    return int(round(float(amount_str) * 100))

def cents_to_dollars(amount_cents):
    return "{:.2f}".format(amount_cents / 100)

@app.route('/', methods=(['GET']))
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM test;")
    result = cursor.fetchall()
    conn.close()

    return result

#CLEAR
@app.route('/clear', methods=(['GET']))
def clear():
    global db_flag
    
    if os.path.exists(db_name):
        os.remove(db_name)
    db_flag = False
    return "Cleared"

#CREATE USER
@app.route('/create_user', methods=(['POST']))
def create_user():
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    first_name = request.form['first_name']
    last_name = request.form['last_name']
    username = request.form['username']
    driver = request.form['driver']
    driver = 1 if str(driver).lower() == 'true' else 0
    deposit = request.form['deposit']
    email_address = request.form['email_address']
    password = request.form['password']
    salt = request.form['salt']
    # Status codes: 1 = success, 2 = username taken, 3 = email taken, 4 = password invalid
    if (not check_user(username)):
        user = json.dumps({"status": 2, "pass_hash": "NULL"})
    elif (not check_email(email_address)):
        user = json.dumps({"status": 3, "pass_hash": "NULL"})
    elif (not (check_pass(password, username, first_name, last_name))):
        user = json.dumps({"status": 4, "pass_hash": "NULL"})
    else:
        password = (password + salt)
        hashed = hashlib.sha256(password.encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, first_name, last_name, email_address, driver, password, salt) VALUES (?, ?, ?, ?, ?, ?, ?);", 
        (username, first_name, last_name, email_address, driver, hashed, salt))
        conn.commit()
        user = json.dumps({"status": 1, "pass_hash": hashed})
        #CREATE PAYMENT ENTRY
        requests.post("http://payments:5000/create_payment", data={'username': username, 'amount': deposit})
        #requests.post("http://localhost:9003/create_payment", data={'username': username, 'amount': deposit})
    
    conn.close()

    return Response(user, mimetype='application/json')

#LOGIN
@app.route('/login', methods=(['POST']))
def login():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    username = request.form['username']
    password = request.form['password']
    cursor.execute("SELECT * FROM users WHERE username = ?;", (username,))
    result = cursor.fetchone()
    # Status codes: 1 = success, 2 = fail
    if (result is None):
        user = json.dumps({"status": 2, "jwt": "NULL"})
    else:
        salt = result[6]
        password = (password + salt)
        hashed = hashlib.sha256(password.encode()).hexdigest()
        if(hashed != result[5]):
            user = json.dumps({"status": 2, "jwt": "NULL"})
        else:
            header = {"alg": "HS256", "typ": "JWT"}
            encoded_header = base64.urlsafe_b64encode(json.dumps(header).encode()).decode()
            payload = {"username": result[0]}
            encoded_payload = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
            signing_input = f"{encoded_header}.{encoded_payload}".encode()
            #secret_key = load_key()
            with open("key.txt") as f:
                secret_key = f.read().strip()
                signature = hmac.new(
                secret_key.encode(),
                signing_input,
                hashlib.sha256
            ).digest()
            jwt = f"{encoded_header}.{encoded_payload}.{signature.hex()}"
            user = json.dumps({"status": 1, "jwt": jwt})
    conn.close()

    return Response(user, mimetype='application/json') 

@app.route('/rate', methods=(['POST']))
def rate():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    username = request.form['username']
    rating = request.form['rating']
    jwt = request.headers['Authorization']
    if not check_jwt(jwt):
        rate = json.dumps({"status": 2})
        conn.close()
        return Response(rate, mimetype='application/json')
    
    rater = get_user(jwt)
    if (rater == username):
        rate = json.dumps({"status": 2})
        conn.close()
        return Response(rate, mimetype='application/json')
    cursor.execute("SELECT driver FROM users WHERE username = ?;", (username,))
    result1 = cursor.fetchone()
    cursor.execute("SELECT driver FROM users WHERE username = ?;", (rater,))
    result2 = cursor.fetchone()
    if result1 is None or result2 is None:
        rate = json.dumps({"status": 2})
        conn.close()
        return Response(rate, mimetype='application/json')
    elif ((result1[0] == 0 and result2[0] == 0) or (result1[0] == 1 and result2[0] == 1)):
        rate = json.dumps({"status": 2})
        conn.close()
        return Response(rate, mimetype='application/json')
     # Check if they have a reservation together
    reservation = requests.get("http://reservations:5000/get_reservation", params={'user1': rater, 'user2': username}, headers={'Authorization': jwt})
    #reservation = requests.get("http://localhost:9002/get_reservation", params={'user1': rater, 'user2': username}, headers={'Authorization': jwt})
    reservation_data = reservation.json()
    if reservation_data['status'] != 1:
        rate = json.dumps({"status": 2})
        conn.close()
        return Response(rate, mimetype='application/json')
    # Add rating
    result = cursor.fetchone()
    cursor.execute("INSERT INTO ratings (username, rating) VALUES (?, ?);", 
        (username, rating))
    conn.commit()
    rate = json.dumps({"status": 1})
    conn.close()

    return Response(rate, mimetype='application/json')

@app.route('/get_user_info', methods=(['GET']))
def get_user_info():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    username = request.args.get('username')
    cursor.execute("SELECT first_name, last_name, email_address, driver FROM users WHERE username = ?;", (username,))
    result = cursor.fetchone()
    if result is None:
        result = json.dumps({"status": 2})
    else:
        result = json.dumps({"status": 1, "first_name": result[0], "last_name": result[1], "email_address": result[2], "driver": result[3]})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/get_total_rating', methods=(['GET']))
def get_total_rating():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()
    username = request.args.get('username')
    cursor.execute("SELECT * FROM ratings WHERE username = ?;", (username,))
    rating = cursor.fetchone()
    if rating is None:
        rating = 0.0
        rating = round(rating, 2)
        rating_str = "{:.2f}".format(rating)
        result = json.dumps({"status": 1, "rating": rating_str})
    else:
        cursor.execute("SELECT AVG(rating) FROM ratings WHERE username = ?;", (username,))
        result = cursor.fetchone()
        if result is None or result[0] is None:
            result = json.dumps({"status": 2})
        else:
            rating = round(result[0], 2)
            rating_str = "{:.2f}".format(rating)
            result = json.dumps({"status": 1, "rating": rating_str})
    conn.close()
    return Response(result, mimetype='application/json')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9000)