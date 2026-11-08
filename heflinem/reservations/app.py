import sqlite3
import os
import json
from flask import Flask, request, Response
import hashlib
import hmac
import base64
import requests


app = Flask(__name__)
db_name = "reservations.db"
sql_file = "reservations.sql"
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

@app.route('/reserve', methods=(['POST']))
def reserve():
    jwt = request.headers['Authorization']
    print("Received JWT header:", repr(jwt))
    if not check_jwt(jwt):
        print(not check_jwt(jwt))
        return Response(json.dumps({"status": 2}), mimetype='application/json')
    
    #make sure it is passenger, and enough money in account (status = 3 if not)
    username = get_user(jwt)

    listingid = request.form['listingid']

    conn = get_db()
    cursor = conn.cursor()
    user = requests.get("http://user:5000/get_user_info", params={'username': username})
    #user = requests.get("http://localhost:9000/get_user_info", params={'username': username})
    data = user.json()
    #MAKE REQUEST TO PAYMENTS SERVICE TO CHECK BALANCE
    if data['driver'] == 1:
        conn.close()
        return Response(json.dumps({"status": 3}), mimetype='application/json')
    balance = requests.get("http://payments:5000/balance", params={'username': username})
    #balance = requests.get("http://localhost:9003/balance", params={'username': username})
    balance_data = balance.json()

    if balance_data['status'] != 1:
        print('balance_data status not 1:', balance_data, flush=True)
        conn.close()
        return Response(json.dumps({"status": 3}), mimetype='application/json')

    price = requests.get("http://availability:5000/get_price", params={'listingid': listingid})
    #price = requests.get("http://localhost:9001/get_price", params={'listingid': listingid})
    price_data = price.json()
    if price_data['status'] != 1:
        print('price_data status not 1:', price_data, flush=True)
        conn.close()
        return Response(json.dumps({"status": 3}), mimetype='application/json')
    price = price_data['price'] #in dollars

    balance_cents = dollars_to_cents(balance_data['amount'])
    price_cents = dollars_to_cents(price)

    if balance_cents <= 0:
        print('insufficient funds: balance_cents <= 0', flush=True)
        conn.close()
        return Response(json.dumps({"status": 3}), mimetype='application/json')
    if balance_cents < price_cents:
        print('insufficient funds: balance_cents < price_cents', flush=True)
        conn.close()
        return Response(json.dumps({"status": 3}), mimetype='application/json')

    requests.post("http://payments:5000/subtract", data={'username': username, 'amount': price})
    #requests.post("http://localhost:9003/subtract", data={'username': username, 'amount': price})

    driver = requests.get("http://availability:5000/get_driver", params={'listingid': listingid})
    #driver = requests.get("http://localhost:9001/get_driver", params={'listingid': listingid})
    driver_data = driver.json()
    driver = driver_data['driver']
    price = dollars_to_cents(price)  #convert to cents for storage
    cursor.execute("INSERT INTO reservations (listingid, passenger, driver, price) VALUES (?, ?, ?, ?);", (listingid, username, driver, price))
    conn.commit()
    requests.post("http://availability:5000/delete_listing", data={'listingid': listingid})
    #requests.post("http://localhost:9001/delete_listing", data={'listingid': listingid})
    conn.close()
    print ("Reservation created for listingid", listingid, "by passenger", username, flush=True)
    return Response(json.dumps({"status": 1}), mimetype='application/json')

#return latest reservations for user
@app.route('/view', methods=(['GET']))
def view():
    jwt = request.headers['Authorization']
    if not check_jwt(jwt):
        return Response(json.dumps({"status": 2, "data": "NULL"}), mimetype='application/json')
    
    username = get_user(jwt)

    conn = get_db()
    cursor = conn.cursor()

    user = requests.get("http://user:5000/get_user_info", params={'username': username})
    #user = requests.get("http://localhost:9000/get_user_info", params={'username': username})
    data = user.json()
    reservations = []
    #find their latest listingid from listings and return whatever is in reservations
    if data['driver'] == 1:
        cursor.execute("SELECT listingid, passenger, price FROM reservations WHERE driver = ? ORDER BY rowid DESC LIMIT 1;", (username,))
        listings = cursor.fetchall()
        listingid = listings[0][0]
        passenger = listings[0][1]
        price = listings[0][2]
        price = cents_to_dollars(price)
        price = "{:.2f}".format(float(price))
        rating = requests.get("http://user:5000/get_total_rating", params={'username': passenger})
        #rating = requests.get("http://localhost:9000/get_total_rating", params={'username': passenger})
        rating_data = rating.json()
        rating = rating_data['rating']
        conn.close()
        return Response(json.dumps({"status": 1, "data": 
            {"listingid": listingid, "price": price, "user": passenger, "rating": rating}}), mimetype='application/json')
    elif data['driver'] == 0:
        cursor.execute("SELECT listingid, driver, price FROM reservations WHERE passenger = ? ORDER BY rowid DESC LIMIT 1;", (username,))
        listings = cursor.fetchall()
        listingid = listings[0][0]
        driver = listings[0][1]
        price = listings[0][2]
        price = cents_to_dollars(price)
        price = "{:.2f}".format(float(price))
        rating = requests.get("http://user:5000/get_total_rating", params={'username': driver})
        #rating = requests.get("http://localhost:9000/get_total_rating", params={'username': driver})
        rating_data = rating.json()
        rating = rating_data['rating']
        conn.close()
        return Response(json.dumps({"status": 1, "data": 
            {"listingid": listingid, "price": price, "user": driver, "rating": rating}}), mimetype='application/json')
    

@app.route('/get_reservation', methods=(['GET']))
def get_reservation():
    jwt = request.headers['Authorization']
    if not check_jwt(jwt):
        return Response(json.dumps({"status": 2}), mimetype='application/json')
    
    user1 = request.args.get('user1')
    user2 = request.args.get('user2')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reservations WHERE (passenger = ? AND driver = ?) OR (driver = ? AND passenger = ?);", (user1, user2, user1, user2))
    reservation = cursor.fetchone()
    if reservation is not None:
        conn.close()
        return Response(json.dumps({"status": 1}), mimetype='application/json')
    else:
        conn.close()
        return Response(json.dumps({"status": 2}), mimetype='application/json')

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=9002)