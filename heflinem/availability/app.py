import sqlite3
import os
import json
from flask import Flask, request, Response
import hashlib
import hmac
import base64
import requests

app = Flask(__name__)
db_name = "listings.db"
sql_file = "listings.sql"
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

@app.route('/listing', methods=(['POST']))
def listing():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    conn.commit()

    jwt = request.headers.get('Authorization')
    if not check_jwt(jwt):
        result = json.dumps({"status": 2})
        conn.close()
        return Response(result, mimetype='application/json')
    username = get_user(jwt)
    user = requests.get("http://user:5000/get_user_info", params={'username': username})
    #user = requests.get("http://localhost:9000/get_user_info", params={'username': username})
    data = user.json()
    if data['status'] != 1:
        result = json.dumps({"status": 2})
        conn.close()
        return Response(result, mimetype='application/json')
    elif data['driver'] == 0:
        result = json.dumps({"status": 2})
        conn.close()
        return Response(result, mimetype='application/json')
    
    day = request.form['day']
    price = request.form['price']
    listingid = request.form['listingid']
    price = dollars_to_cents(price)
    cursor.execute("INSERT INTO listings (listingid, username, day, price) VALUES (?, ?, ?, ?);", 
        (listingid, username, day, price))
    conn.commit()
    listing = json.dumps({"status": 1})
    conn.close()
    return Response(listing, mimetype='application/json')

@app.route('/search', methods=(['GET']))
def search():
    conn = get_db()
    cursor = conn.cursor()
    jwt = request.headers.get('Authorization')
    if not check_jwt(jwt):
        result = json.dumps({"status": 2, "data": []})
        conn.close()
        return Response(result, mimetype='application/json')
    result = requests.get("http://user:5000/get_user_info", params={'username': get_user(jwt)})
    #result = requests.get("http://localhost:9000/get_user_info", params={'username': get_user(jwt)})
    data = result.json()
    if data is None:
        result = json.dumps({"status": 2, "data": []})
        conn.close()
        return Response(result, mimetype='application/json')
    elif data['status'] != 1:
        result = json.dumps({"status": 2, "data": []})
        conn.close()
        return Response(result, mimetype='application/json')
    elif data['driver'] == 1:
        result = json.dumps({"status": 2, "data": []})
        conn.close()
        return Response(result, mimetype='application/json')
    day = request.args.get('day')
    cursor.execute("SELECT listingid, username, day, price FROM listings WHERE day = ?;", 
        (day,))
    results = cursor.fetchall()
    listings = []
    for row in results:
        rating = requests.get("http://user:5000/get_total_rating", params={'username': row[1]})
        #rating = requests.get("http://localhost:9000/get_total_rating", params={'username': row[1]})
        rating_data = rating.json()
        rating = rating_data['rating']
        price = cents_to_dollars(row[3])  #convert to dollars
        listing = {
            "listingid": row[0],
            "price": price,
            "driver": row[1],
            "rating": rating
        }
        listings.append(listing)
    result = json.dumps({"status": 1, "data": listings})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/get_availability', methods=(['POST']))
def get_availability():
    conn = get_db()
    cursor = conn.cursor()
    username = request.form['username']
    cursor.execute("SELECT listingid, day, price FROM listings WHERE username = ?;", 
        (username,))
    results = cursor.fetchall()
    listings = []
    for row in results:
        price = cents_to_dollars(row[2])  #convert to dollars
        listing = {
            "listingid": row[0],
            "day": row[1],
            "price": price
        }
        listings.append(listing)
    result = json.dumps({"status": 1, "data": listings})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/get_price', methods=(['GET']))
def get_price():
    conn = get_db()
    cursor = conn.cursor()
    listingid = request.args.get('listingid')
    cursor.execute("SELECT price FROM listings WHERE listingid = ?;", 
        (listingid,))
    result = cursor.fetchone()
    if result is None:
        result = json.dumps({"status": 2})
    else:
        price_dollars = cents_to_dollars(result[0])  #convert to dollars
        result = json.dumps({"status": 1, "price": price_dollars})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/get_driver', methods=(['GET']))
def get_driver():
    conn = get_db()
    cursor = conn.cursor()
    listingid = request.args.get('listingid')
    cursor.execute("SELECT username FROM listings WHERE listingid = ?;", 
        (listingid,))
    result = cursor.fetchone()
    if result is None:
        result = json.dumps({"status": 2})
    else:
        driver = result[0]
        result = json.dumps({"status": 1, "driver": driver})
    conn.close()
    return Response(result, mimetype='application/json')

@app.route('/delete_listing', methods=(['POST']))
def delete_listing():
    conn = get_db()
    cursor = conn.cursor()
    listingid = request.form['listingid']
    cursor.execute("DELETE FROM listings WHERE listingid = ?;", 
        (listingid,))
    conn.commit()
    conn.close()
    return Response(json.dumps({"status": 1}), mimetype='application/json')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9001)