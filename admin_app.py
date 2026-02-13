#!/usr/bin/env python3
from flask import Flask, render_template, jsonify, request
import subprocess
import os
import time
import logging

app = Flask(__name__)

logging.basicConfig(
    filename='/tmp/tw404_admin_app.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

SOLARIS_HOST = os.environ.get('SOLARIS_HOST', 'solaris')

def run_ssh(cmd, timeout=10):
    try:
        ssh_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-q',
            SOLARIS_HOST,
            cmd
        ]
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            timeout=timeout,
            text=True
        )
        return result.returncode == 0, result.stdout or "", result.stderr or ""
    except Exception as e:
        return False, "", str(e)

@app.route('/')
def dashboard():
    return render_template('admin_dashboard.html')

# -----------------------------
# STATUS
# -----------------------------
@app.route('/api/admin/status')
def status():
    try:
        ok_db, out_db, _ = run_ssh("pgrep -f 'db -d 12'")
        ok_j0, out_j0, _ = run_ssh("pgrep -f 'jtales0'")
        ok_j1, out_j1, _ = run_ssh("pgrep -f 'jtales1'")
        ok_j2, out_j2, _ = run_ssh("pgrep -f 'jtales2'")

        return jsonify({
            'db': bool(out_db.strip()),
            'jtales0': bool(out_j0.strip()),
            'jtales1': bool(out_j1.strip()),
            'jtales2': bool(out_j2.strip()),
            'timestamp': time.time()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -----------------------------
# START / STOP / RESTART
# -----------------------------
@app.route('/api/admin/start', methods=['POST'])
def start_servers():
    try:
        run_ssh("pkill -9 db; pkill -9 jtales")
        time.sleep(1)

        run_ssh("cd /tw404/db && nohup ./db -d 12 > db.log 2>&1 &")
        time.sleep(2)

        run_ssh("cd /tw404/jtales0 && nohup ./start0 > logs/jtales0.log 2>&1 &")
        run_ssh("cd /tw404/jtales0 && nohup ./start1 > logs/jtales1.log 2>&1 &")
        run_ssh("cd /tw404/jtales0 && nohup ./start2 > logs/jtales2.log 2>&1 &")

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/admin/stop', methods=['POST'])
def stop_servers():
    run_ssh("pkill -9 db; pkill -9 jtales")
    return jsonify({'success': True})

@app.route('/api/admin/restart', methods=['POST'])
def restart_servers():
    run_ssh("pkill -9 db; pkill -9 jtales")
    time.sleep(2)
    return start_servers()

# -----------------------------
# LOGS
# -----------------------------
@app.route('/api/admin/logs/<server>')
def get_logs(server):
    paths = {
        "db": "/tw404/db/db.log",
        "jtales0": "/tw404/jtales0/logs/jtales0.log",
        "jtales1": "/tw404/jtales0/logs/jtales1.log",
        "jtales2": "/tw404/jtales0/logs/jtales2.log"
    }
    if server not in paths:
        return jsonify({'error': 'Invalid server'}), 400

    ok, out, err = run_ssh(f"tail -200 {paths[server]} 2>/dev/null")
    return jsonify({'log': out if ok else err})

# -----------------------------
# GM ACCOUNT ASSIGNMENT
# -----------------------------
@app.route('/api/admin/set-gm', methods=['POST'])
def set_gm():
    data = request.json
    name = data.get('name', '').strip()
    ip = data.get('ip', '').strip()

    if not name or not ip:
        return jsonify({'error': 'Missing name or IP'}), 400

    script = f"""
cd /tw404
UH=db/master/uh

ID_FILE=$($UH -n -l 2 -g jtales {name})
if [ ! -f "/tw404/db/master/$ID_FILE" ]; then
    echo "ERROR: No such account"
    exit 1
fi

PASS=$(grep password= /tw404/db/master/$ID_FILE | cut -d= -f2 | tr -d '"')

for i in 0 1 2; do
    echo -e "i\\t{ip}\\t255.255.255.255" >> /tw404/jtales0/console.conf
    echo -e "m\\t{name}\\t$PASS" >> /tw404/jtales0/console.conf
done

echo "SUCCESS"
"""

    ok, out, err = run_ssh(f"bash -s << 'EOF'\n{script}\nEOF", timeout=15)
    return jsonify({'success': ok, 'output': out or err})

# -----------------------------
# IP BAN LIST
# -----------------------------
@app.route('/api/admin/ban-ip', methods=['POST'])
def ban_ip():
    data = request.json
    ip = data.get('ip', '').strip()

    if not ip:
        return jsonify({'error': 'Missing IP'}), 400

    ok, out, err = run_ssh(f"echo 'b {ip}' >> /tw404/jtales0/banip.conf")
    return jsonify({'success': ok})

@app.route('/api/admin/ban-list')
def ban_list():
    ok, out, err = run_ssh("cat /tw404/jtales0/banip.conf 2>/dev/null")
    return jsonify({'list': out.splitlines() if ok else []})

# -----------------------------
# CORS
# -----------------------------
@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8081, debug=False)

