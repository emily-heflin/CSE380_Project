DROP TABLE IF EXISTS reservations;

CREATE TABLE reservations (listingid INTEGER PRIMARY KEY,
    driver TEXT,
    passenger TEXT,
    price INTEGER);