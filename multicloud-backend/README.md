# MultiCloud Backend — Local Setup Guide

## Files in this folder
```
multicloud-backend/
├── app.py           ← Main Flask server
├── vm_routes.py     ← AWS / Azure / GCP VM endpoints
├── requirements.txt ← Python dependencies
├── start.bat        ← Double-click to run (Windows)
├── start.sh         ← Run in terminal (Mac/Linux)
└── README.md        ← This file
```

---

## Step 1 — Make sure Python is installed
Open Command Prompt / Terminal and run:
```
python --version
```
You should see `Python 3.8+`. If not, download from https://python.org

---

## Step 2 — Run the backend

### Windows (easiest):
Double-click `start.bat`

### OR manually in Command Prompt:
```
cd multicloud-backend
pip install -r requirements.txt
python app.py
```

You should see:
```
==================================================
  MultiCloud Backend Running!
  URL: http://localhost:5000
  Health: http://localhost:5000/api/health
==================================================
```

---

## Step 3 — Test it's working
Open your browser and go to:
```
http://localhost:5000/api/health
```
You should see: `{"status": "ok", "service": "MultiCloud VM Manager"}`

---

## Step 4 — Install & run ngrok (so your website can reach localhost)

1. Download ngrok from https://ngrok.com/download
2. Sign up free at https://ngrok.com
3. Copy your authtoken from the ngrok dashboard
4. Run:
   ```
   ngrok config add-authtoken YOUR_TOKEN_HERE
   ngrok http 5000
   ```
5. Copy the `https://xxxx.ngrok-free.app` URL shown

---

## Step 5 — Update your index.html
Find this line in your index.html VM Manager JS:
```js
var VM_API = 'https://your-flask-app.onrender.com';
```
Replace with your ngrok URL:
```js
var VM_API = 'https://xxxx.ngrok-free.app';
```
Push to GitHub. Done!

---

## API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET  | /api/health | Check server is running |
| POST | /api/aws/vms/list | List EC2 instances |
| POST | /api/aws/vms/create | Create EC2 instance |
| POST | /api/aws/vms/action | Start/Stop/Reboot/Terminate |
| POST | /api/azure/vms/list | List Azure VMs |
| POST | /api/azure/vms/action | Start/Stop/Restart/Delete |
| POST | /api/gcp/vms/list | List GCP instances |
| POST | /api/gcp/vms/create | Create GCP instance |
| POST | /api/gcp/vms/action | Start/Stop/Reset/Delete |
