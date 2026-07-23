import os
import base64
import random
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BASE_URL = "https://exam.prsuuniv.in"

def encode_b64(value):
    return base64.b64encode(str(value).encode('utf-8')).decode('utf-8')

def get_result_redirect_url(roll_number):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    studentty_b64 = encode_b64("REGULAR")
    semester_b64 = encode_b64("4")
    coursename_b64 = encode_b64("Bachelor of Education")
    
    salted_roll = f"{random.randint(1000, 9999)}{roll_number}@@{random.randint(1000, 9999)}"
    examroll_b64 = encode_b64(salted_roll)

    endpoint = f"{BASE_URL}/prsuresult/home/student/result/msw/check19/{semester_b64}/{studentty_b64}/{examroll_b64}/{coursename_b64}/resultrack"

    response = session.get(endpoint)
    data = response.json()

    if data.get("status") in [1, 2]:
        if data.get("status") == 2:
            try:
                msg_parts = data.get("message", "").split("@")
                ansidrno, student_id, name = msg_parts[0], msg_parts[1], msg_parts[2]
                
                abc_url = f"{BASE_URL}/prsuform/abcidfromenroll"
                abc_res = session.get(abc_url, params={"ansidrno": ansidrno, "student_id": student_id, "name": name}).json()

                if abc_res and len(abc_res) > 0:
                    rec = abc_res[0]
                    session.post(f"{BASE_URL}/prsuresult/student/updateResultAbcid", data={
                        "abcid": rec.get("abcid"),
                        "ansidrno": rec.get("ansidrno"),
                        "student_id": rec.get("student_id")
                    })
            except Exception as e:
                print(f"ABC ID step skipped: {e}")

        redirect_path = data.get("redirect", "").strip('"')
        return f"{BASE_URL}{redirect_path}"

    return None

@app.route('/get-result-url', methods=['POST', 'OPTIONS'])
def get_url():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    data = request.get_json(force=True)
    roll_number = data.get("roll_number")

    if not roll_number:
        return jsonify({"error": "Roll number is required"}), 400

    result_url = get_result_redirect_url(roll_number)

    if result_url:
        return jsonify({"success": True, "result_url": result_url})
    else:
        return jsonify({"success": False, "error": "Result not found"}), 404

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
