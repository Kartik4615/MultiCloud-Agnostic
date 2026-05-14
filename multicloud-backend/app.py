from flask import Flask
from flask_cors import CORS
from vm_routes import vm_bp

app = Flask(__name__)
CORS(app)  # Allow all origins (fine for local dev)

# Register VM Manager routes
app.register_blueprint(vm_bp)

if __name__ == '__main__':
    print("=" * 50)
    print("  MultiCloud Backend Running!")
    print("  URL: http://localhost:5000")
    print("  Health: http://localhost:5000/api/health")
    print("=" * 50)
    app.run(debug=True, port=5000)
