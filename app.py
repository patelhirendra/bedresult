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

# Map frontend selection keys to exact PRSU portal parameters
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

def get_result_redirect_url(roll_number, course_key):
    course_info = COURSE_MAP.get(course_key)
    if not course_info:
        return None

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })

    # Encode course parameters using standard Base64 encoding
    studentty_b64 = encode_b64(course_info["studentty"])
    semester_b64 = encode_b64(course_info["semester"])
    coursename_b64 = encode_b64(course_info["coursename"])
    
    # Salt formula matching PRSU client-side JS: 4_random_digits + roll + "@@" + 4_random_digits
    salted_roll = f"{random.randint(1000, 9999)}{roll_number}@@{random.randint(1000, 9999)}"
    examroll_b64 = encode_b64(salted_roll)

    endpoint = f"{BASE_URL}/prsuresult/home/student/result/msw/check19/{semester_b64}/{studentty_b64}/{examroll_b64}/{coursename_b64}/resultrack"

    try:
        response = session.get(endpoint, timeout=15)
        data = response.json()

        if data.get("status") in [1, 2]:
            # Handle status == 2 (ABC ID Check / Verification flow)
            if data.get("status") == 2:
                try:
                    msg_parts = data.get("message", "").split("@")
                    ansidrno = msg_parts[0] if len(msg_parts) > 0 else ""
                    student_id = msg_parts[1] if len(msg_parts) > 1 else ""
                    name = msg_parts[2] if len(msg_parts) > 2 else ""
                    dob = msg_parts[3] if len(msg_parts) > 3 else ""

                    abc_url = f"{BASE_URL}/prsuform/abcidfromenroll"
                    abc_res = session.get(
                        abc_url, 
                        params={
                            "ansidrno": ansidrno, 
                            "student_id": student_id, 
                            "name": name,
                            "dob": dob
                        },
                        timeout=10
                    ).json()

                    if abc_res and isinstance(abc_res, list) and len(abc_res) > 0:
                        rec = abc_res[0]
                        verified_abcid = rec.get("abcid")
                        
                        if verified_abcid:
                            session.post(
                                f"{BASE_URL}/prsuresult/student/updateResultAbcid", 
                                data={
                                    "abcid": verified_abcid,
                                    "ansidrno": rec.get("ansidrno"),
                                    "student_id": rec.get("student_id")
                                },
                                timeout=10
                            )
                except Exception as e:
                    print(f"[!] ABC ID verification attempt bypassed: {e}")

            # Extract destination path and assemble full redirect URL
            redirect_path = data.get("redirect", "").strip('"')
            return f"{BASE_URL}{redirect_path}"

    except Exception as err:
        print(f"[!] Error making request to PRSU: {err}")

    return None

@app.route('/get-result-url', methods=['POST', 'OPTIONS'])
def get_url():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(force=True)
        roll_number = data.get("roll_number")
        course_key = data.get("course_key", "bed_4")

        if not roll_number:
            return jsonify({"error": "Roll number is required"}), 400

        result_url = get_result_redirect_url(roll_number, course_key)

        if result_url:
            return jsonify({"success": True, "result_url": result_url})
        else:
            return jsonify({"success": False, "error": "Result not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
