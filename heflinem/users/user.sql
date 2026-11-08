DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS ratings;

CREATE TABLE users (username TEXT PRIMARY KEY, 
    first_name TEXT, 
    last_name TEXT, 
    email_address TEXT UNIQUE, 
    driver BOOLEAN,
    password TEXT, 
    salt TEXT);

CREATE TABLE ratings (username TEXT, 
    rating INTEGER,
    FOREIGN KEY(username) REFERENCES users(username));
