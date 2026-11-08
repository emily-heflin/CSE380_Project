# CSE380_Project
Final Project CSE 380

## About the Project
This project is a scaled-down, Uber-style ride-hailing system built with Python and Flask and run entirely on a local machine with Docker Compose. It replicates the flow of a ride-hailing app. Riders request trips, drivers are matched, rides are tracked, and fares are calculated. Users can rate other users. The system is split into four independent microservices that communicate over REST APIs, which makes it a practical way to learn service-oriented architecture, containerization, and inter-service communication without cloud costs.

## Four Microservices
1. Users Service (port user:5000)
Handles registration, login, and profiles for riders and drivers. It stores basic details, driver vehicle info, and issues authentication tokens. Other services call it to confirm that a user exists and has the right role.

2. Availability Service (port availability:5000)
Tracks which drivers are free on a given day. It exposes an endpoint that returns available drivers based on price and day. Other services call it to match a user to a driver from the listings.

3. Reservations Service (port reservations:5000)
The core of the system. When a rider books a ride, this service validates the rider with the Users Service, asks the Availability Service for a matching driver, asks the Payment Service for information making sure the user has a sufficient balance, and creates the reservation. It marks the driver as unavailable while a ride is active and frees them afterward.

4. Payments Service (port payments:5000)
Calculates fares from prices in listings and records simulated payments. Users can add to their balance and a reservation will update and subtract from their current balance.

## Architecture
Containerization: Each service has its own Dockerfile and runs in its own container.

Orchestration: One docker-compose.yml starts everything on a shared network, so services reach each other by name.

Data storage: Each service owns its own database.

Communication: Synchronous HTTP/JSON calls between services using the requests library.
