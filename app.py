import os
import base64
import random
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
# Enable CORS for all routes so GitHub Pages can call this API
CORS(app, resources={r"/*": {"origins": "*"}})

BASE_URL = "https://exam.prsuuniv.in"

def encode_b64(value):
    return base64.b64encode(str(value).encode('utf-8')).decode('utf-8')

# Payload configuration for the supported courses
COURSE_MAP = {
    "bed_4": {
        "coursename": "Bachelor of Education",
        "semester": "4",
        "studentty": "REGULAR"
    },
    "msc_botany_2": {
        "coursename": "Master of Science in Botany",
        "semester": "2",
        "studentty": "REGULAR"
    }
}

@app.route('/get-result-url', methods=['POST', 'OPTIONS'])
def get_result_url():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}
        roll_number = str(data.get("roll_number", "")).strip()
        course_key = data.get("course_key", "bed_4")

        if not roll_number:
            return jsonify({"success": False, "error": "Roll number is required"}), 400

        course_info = COURSE_MAP.get(course_key)
        if not course_info:
            return jsonify({"success": False, "error": "Invalid course selected"}), 400

        # Base64 encoding parameters matching PRSU client-side script
        studentty_b64 = encode_b64(course_info["studentty"])
        semester_b64 = encode_b64(course_info["semester"])
        coursename_b64 = encode_b64(course_info["coursename"])
        
        # Salted roll number: 4_digits + roll + "@@" + 4_digits
        salted_roll = f"{random.randint(1000, 9999)}{roll_number}@@{random.randint(1000, 9999)}"
        examroll_b64 = encode_b64(salted_roll)

        endpoint = f"{BASE_URL}/prsuresult/home/student/result/msw/check19/{semester_b64}/{studentty_b64}/{examroll_b64}/{coursename_b64}/resultrack"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Make direct HTTP request to get result payload
        response = requests.get(endpoint, headers=headers, timeout=15)
        res_data = response.json()

        # Extract redirect path regardless of status (1 or 2)
        redirect_path = res_data.get("redirect")
        if redirect_path:
            redirect_path = redirect_path.strip('"')
            full_url = f"{BASE_URL}{redirect_path}"
            return jsonify({"success": True, "result_url": full_url}), 200
        else:
            return jsonify({"success": False, "error": "Result not found on PRSU server."}), 404

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"success": False, "error": "Failed to connect to PRSU server."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
