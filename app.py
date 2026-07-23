import os
import time
import base64
import asyncio
from flask import Flask, request, send_file, jsonify, make_response
from flask_cors import CORS
from playwright.async_api import async_playwright

app = Flask(__name__)

# Initialize CORS globally for all routes and origins
CORS(app, resources={r"/*": {"origins": "*"}})

# Force-inject CORS headers into EVERY response (including errors & preflights)
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

BASE_URL = "https://exam.prsuuniv.in"
LOGIN_URL = f"{BASE_URL}/prsuresult/login"

async def fetch_and_generate_pdf(roll_number):
    output_filename = f"Result_{roll_number}.pdf"
    
    async with async_playwright() as p:
        # Launch Chromium with extra flags for containerized server environments
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
        )
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        try:
            # 1. Open Portal
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)

            # 2. Open Result Modal
            await page.click("#result_section2019")
            await page.wait_for_selector("#coursename", timeout=15000)

            # 3. Select Form Details
            await page.select_option("#coursename", "Bachelor of Education")
            await page.select_option("#studentty", "REGULAR")
            await page.select_option("#semyr", "4")

            # 4. Input Roll Number
            await page.fill("#examroll", str(roll_number))

            # 5. Execute AJAX & Handle ABC ID Verification
            js_script = """
                return new Promise((resolve) => {
                    var studentty = btoa($('#studentty').val()); 
                    var semester = btoa($('#semyr').val()); 
                    var examroll = btoa(Math.floor(1000 + Math.random() * 9000) + $('#examroll').val() + "@@" + Math.floor(1000 + Math.random() * 9000));
                    var coursename = btoa($('#coursename').val());
                    
                    var urlname = "/prsuresult/home/student/result/msw/check19/" + semester + "/" + studentty + "/" + examroll + "/" + coursename + "/resultrack";
                    
                    $.ajax({
                        url: urlname,
                    }).done(function(data) {
                        if (typeof data === "string") { data = JSON.parse(data); }
                        
                        if (data.status == 1 || data.status == 2) {
                            resolve({success: true, redirect: data.redirect});
                        } else {
                            resolve({success: false, message: "Result not found"});
                        }
                    }).fail(function() {
                        resolve({success: false, message: "AJAX Request Failed"});
                    });
                });
            """
            
            res = await page.evaluate(js_script)

            if res.get("success"):
                redirect_path = res.get("redirect", "").strip('"')
                full_url = f"{BASE_URL}{redirect_path}"

                await page.goto(full_url, wait_until="networkidle", timeout=30000)
                
                pdf_bytes = await page.pdf(
                    format="A4",
                    print_background=True,
                    margin={"top": "0px", "bottom": "0px", "left": "0px", "right": "0px"}
                )

                with open(output_filename, "wb") as f:
                    f.write(pdf_bytes)

                await browser.close()
                return output_filename
            else:
                await browser.close()
                return None

        except Exception as e:
            print(f"Error during Playwright execution: {e}")
            await browser.close()
            return None

# CRUCIAL FIX: Allow both POST and OPTIONS explicitly on the route
@app.route('/download-result', methods=['POST', 'OPTIONS'])
def download():
    # Instantly answer browser preflight check
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(force=True)
        roll_number = data.get("roll_number")

        if not roll_number:
            return jsonify({"error": "Roll number is required"}), 400

        pdf_path = asyncio.run(fetch_and_generate_pdf(roll_number))

        if pdf_path and os.path.exists(pdf_path):
            return send_file(
                pdf_path,
                as_attachment=True,
                download_name=f"Result_{roll_number}.pdf",
                mimetype="application/pdf"
            )
        else:
            return jsonify({"error": "Result not found or university server error"}), 404

    except Exception as e:
        print(f"Unhandled Exception: {e}")
        return jsonify({"error": "Internal Server Error"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
