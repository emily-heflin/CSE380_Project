DROP TABLE IF EXISTS listings;

CREATE TABLE listings (listingid INTEGER, 
    username TEXT,
    day TEXT,
    price INTEGER,
    PRIMARY KEY(listingid, username));