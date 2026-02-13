import requests

def test_audit():
    # Attempt to login first to get a token
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_data = {
        "email": "abdelilahourti@gmail.com", # From .env email
        "password": "1234" # Guessing or from common seeds
    }
    
    try:
        r = requests.post(login_url, json=login_data)
        if r.status_code != 200:
            print(f"Login failed: {r.status_code} {r.text}")
            return
        
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        audit_url = "http://localhost:8000/api/v1/system/audit"
        r = requests.get(audit_url, headers=headers)
        print(f"Audit Status: {r.status_code}")
        if r.status_code == 200:
            print(f"Found {len(r.json())} logs")
        else:
            print(f"Error: {r.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_audit()
