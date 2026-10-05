import requests

try:
    # 1. Test Duplicate Registration
    r_dup = requests.post("http://localhost:8000/api/auth/register", json={
        "name": "Test User", "email": "test2@example.com", "password": "password"
    })
    print("Duplicate Registration Test:")
    print("Status:", r_dup.status_code)
    print("Response:", r_dup.json())
    
    # 2. Test Login
    r_login = requests.post("http://localhost:8000/api/auth/login", data={
        "username": "test2@example.com",
        "password": "password"
    })
    print("\nLogin Test:")
    print("Status:", r_login.status_code)
    
except Exception as e:
    print(e)
