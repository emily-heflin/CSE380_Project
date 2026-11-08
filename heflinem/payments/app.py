import sqlite3
import os
import json
from flask import Flask, request, Response
import hashlib
import hmac
import base64
import requests
import sys

app = Flask(__name__)
db_name = "payments.db"
sql_file = "payments.sql"
db_flag = False

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
    global db_flag
    if not db_flag:
        create_db()
    conn = sqlite3.connect(db_name)
    return conn


def dollars_to_cents(amount_str):
	return int(round(float(amount_str) * 100))

def cents_to_dollars(amount_cents):
	return "{:.2f}".format(amount_cents / 100)

#CLEAR
@app.route('/clear', methods=(['GET']))
def clear():
    global db_flag
    
    if os.path.exists(db_name):
        os.remove(db_name)
    db_flag = False
    return "Cleared"

@app.route('/add', methods=(['POST']))
def add():
    conn = get_db()
    cursor = conn.cursor()

    jwt = request.headers['Authorization']
    if not check_jwt(jwt):
        conn.close()
        return Response(json.dumps({"status": 2}), mimetype='application/json')
    
    username = get_user(jwt)

    amount = request.form['amount']
    amount = dollars_to_cents(amount)  #convert to cents
    cursor.execute("SELECT amount FROM payments WHERE username = ?;", (username,))
    result = cursor.fetchone()
    new_amount = amount + result[0]
    cursor.execute("UPDATE payments SET amount = ? WHERE username = ?;", (new_amount, username))
    conn.commit()
    conn.close()
    return Response(json.dumps({"status": 1}), mimetype='application/json')

@app.route('/view', methods=(['GET']))
def view():
    conn = get_db()
    cursor = conn.cursor()
    print("View called", file=sys.stderr)

    jwt = request.headers.get('Authorization')
    if not check_jwt(jwt):
        print("Invalid JWT", flush=True)
        conn.close()
        return Response(json.dumps({"status": 2, "balance": "NULL"}), mimetype='application/json')
    
    username = get_user(jwt)

    cursor.execute("SELECT amount FROM payments WHERE username = ?;", (username,))
    result = cursor.fetchone()
    if result is None:
        print ("No payment record found for user", username, flush=True)
        result = json.dumps({"status": 2, "balance": "NULL"})
    else:
        amount_dollars = cents_to_dollars(result[0])  #convert to dollars
        result = json.dumps({"status": 1, "balance": amount_dollars})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/create_payment', methods=(['POST']))
def create_payment():
    conn = get_db()
    cursor = conn.cursor()

    username = request.form['username']
    amount = request.form['amount']
    amount = dollars_to_cents(amount)  #convert to cents

    cursor.execute("INSERT INTO payments (username, amount) VALUES (?, ?);", 
        (username, amount))
    conn.commit()
    conn.close()

    return Response(json.dumps({"status": 1}), mimetype='application/json')

@app.route('/balance', methods=(['GET']))
def balance():
    conn = get_db()
    cursor = conn.cursor()

    username = request.args.get('username')

    cursor.execute("SELECT amount FROM payments WHERE username = ?;", (username,))
    result = cursor.fetchone()
    if result is None:
        result = json.dumps({"status": 2})
    else:
        amount_dollars = cents_to_dollars(result[0])  #convert to dollars
        result = json.dumps({"status": 1, "amount": amount_dollars})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/subtract', methods=(['POST']))
def subtract():
    conn = get_db()
    cursor = conn.cursor()

    username = request.form['username']
    amount = request.form['amount']
    amount = dollars_to_cents(amount)  #convert to cents
    print(f"Subtract called for {username} with {amount}", flush=True)

    cursor.execute("SELECT amount FROM payments WHERE username = ?;", (username,))
    result = cursor.fetchone()
    if result is None or result[0] < amount:
        conn.close()
        return Response(json.dumps({"status": 2}), mimetype='application/json')
    print (f"Current amount for {username} is {result[0]}", flush=True)
    new_amount = result[0] - amount
    print (f"New amount for {username} is {new_amount}", flush=True)
    cursor.execute("UPDATE payments SET amount = ? WHERE username = ?;", (new_amount, username))
    conn.commit()
    conn.close()
    return Response(json.dumps({"status": 1}), mimetype='application/json')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9003)