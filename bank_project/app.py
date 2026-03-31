from flask import Flask, request, jsonify, send_file, render_template
import subprocess, os
import pandas as pd

app = Flask(__name__)

# -------------------------------
# Mock Bank Users
# -------------------------------
users = {
    "sbi_user":   {"password": "1234", "bank": "SBI",   "csv": "data_sbi.csv"},
    "hdfc_user":  {"password": "1234", "bank": "HDFC",  "csv": "data_hdfc.csv"},
    "icici_user": {"password": "1234", "bank": "ICICI", "csv": "data_icici.csv"}
}

# -------------------------------
# Folders
# -------------------------------
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -------------------------------
# ROUTES
# -------------------------------

@app.route('/')
def home():
    """Render homepage"""
    return render_template("index.html")


@app.route('/login', methods=['POST'])
def login():
    """Login route for banks"""
    data = request.json
    userid = data.get("userid")
    password = data.get("password")

    if userid in users and users[userid]["password"] == password:
        bank = users[userid]["bank"]
        csv_path = users[userid]["csv"]
        return jsonify({
            "status": "success",
            "message": f"Welcome {bank} user!",
            "bank": bank,
            "csv_file": csv_path
        })
    return jsonify({"status": "error", "message": "Invalid credentials"}), 401


@app.route('/upload', methods=['POST'])
def upload():
    """Upload CSV manually"""
    file = request.files['file']
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    file.save(filepath)
    return jsonify({"status": "uploaded", "csv_path": filepath})


@app.route('/analyze', methods=['POST'])
def analyze():
    """Run backend analyzer"""
    data = request.json
    csv_path = data.get("csv_path")

    if not os.path.exists(csv_path):
        return jsonify({"status": "error", "message": f"File not found: {csv_path}"}), 404

    subprocess.run(["python", "analyze_money_trail.py", "--input", csv_path, "--outdir", OUTPUT_DIR])
    return jsonify({
        "status": "done",
        "output_csv": os.path.join(OUTPUT_DIR, "suspicious_accounts.csv"),
        "network_graph": os.path.join(OUTPUT_DIR, "network_plot.png")
    })


@app.route('/get_results/<path:filename>')
def get_results(filename):
    """Show CSV or PNG inline in browser"""
    full_path = os.path.join(OUTPUT_DIR, filename)
    print("DEBUG -> Requested:", full_path)

    if not os.path.exists(full_path):
        return f"⚠️ File not found at: {full_path}", 404

    ext = os.path.splitext(full_path)[1].lower()

    # ---- CSV to HTML ----
    if ext == ".csv":
        try:
            df = pd.read_csv(full_path)
            return render_template("result.html",
                                   tables=[df.to_html(classes='data', header=True, index=False)])
        except Exception as e:
            return f"<pre>Could not read CSV: {e}</pre>", 500

    # ---- Image inline ----
    elif ext in [".png", ".jpg", ".jpeg"]:
        return send_file(full_path, mimetype="image/png", as_attachment=False)

    # ---- Fallback ----
    else:
        return send_file(full_path, as_attachment=False)


if __name__ == "__main__":
    app.run(debug=True)
