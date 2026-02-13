#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify
import subprocess
import os
import time
from datetime import datetime
import logging
import shlex

app = Flask(__name__)

# Log account creation attempts
logging.basicConfig(
    filename='/tmp/tw404_accounts.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# Solaris SSH alias (set in ~/.ssh/config)
SOLARIS_HOST = os.environ.get('SOLARIS_HOST', 'solaris')

# Default TW404 account parameters
EMAIL = 'twsrv@localhost'
BIRTHDATE = '19990909'
RNAME = '1'
SOLAR = '4'
GENDER = '5'

@app.route('/')
def index():
    return render_template('account_creation.html')

@app.route('/api/health')
def health():
    """Check SSH connectivity to Solaris server."""
    try:
        result = subprocess.run(
            [
                'ssh',
                '-o', 'ConnectTimeout=3',
                '-o', 'BatchMode=yes',
                SOLARIS_HOST,
                'test -d /tw404'
            ],
            capture_output=True,
            timeout=5
        )
        connected = result.returncode == 0

        return jsonify({
            'status': 'ok' if connected else 'offline',
            'solaris_connected': connected
        })

    except subprocess.TimeoutExpired:
        return jsonify({'status': 'timeout', 'solaris_connected': False})
    except Exception as e:
        app.logger.exception('Health check error')
        return jsonify({'status': 'error', 'solaris_connected': False, 'error': str(e)})

@app.route('/api/create-account', methods=['POST'])
def create_account():
    """Create a normal end-user account (public-facing)."""
    data = request.json
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()

    # Basic validation
    if len(name) < 3:
        return jsonify({'error': 'Account name must be 3+ characters'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be 6+ characters'}), 400

    try:
        name_q = shlex.quote(name)
        passwd_q = shlex.quote(password)

        # SSH script faithfully replicating create-accounts logic
        ssh_script = f"""
cd /tw404
TWSRV_DIR=$(pwd)
TALES_NAME=$(ls | grep tales0 | sed 's/[0-9]//g' || true)

EMAIL="{EMAIL}"
BIRTHFAY="{BIRTHDATE}"
RNAME="{RNAME}"
SOLAR="{SOLAR}"
GENDER="{GENDER}"

CREATEDATE=$(date +"%Y%m%d")
TICK=$(expr $(date +"%Y") + 1)
CREATETICK=$(date +"$TICK%m%d")

UH=$TWSRV_DIR/db/master/uh

# Determine TAG and SRC (jtales vs ttales)
if [ "$TALES_NAME" = "jtales" ]; then
    SRC=$($UH -n -l 2 -g ttales {name_q})
    TAG=$($UH -n -l 2 -g jtales {name_q})
else
    SRC=""
    TAG=$($UH -n -l 2 -g ttales {name_q})
fi

DST=$(dirname $TAG)
CHECK=$TWSRV_DIR/db/master/$TAG

# Check if account already exists
if [ -f "$CHECK" ]; then
    echo "ERROR: Account already exists at $CHECK"
    exit 1
fi

# Create account
cd $TWSRV_DIR/db/master
./create_master {name_q} {passwd_q} "$EMAIL" "$BIRTHFAY" "$RNAME" "$CREATEDATE" "$CREATETICK" "$SOLAR" "$GENDER"

# Move file if needed (jtales mode)
if [ "$TALES_NAME" = "jtales" ] && [ -n "$SRC" ]; then
    mv "$SRC" "$DST" 2>/dev/null || true
fi

# Verify creation
if [ -f "$CHECK" ]; then
    echo "SUCCESS: $CHECK"
    exit 0
else
    echo "ERROR: creation failed, $CHECK not found"
    exit 2
fi
"""

        ssh_args = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-q',
            SOLARIS_HOST,
            'bash', '-s'
        ]

        result = subprocess.run(
            ssh_args,
            input=ssh_script,
            capture_output=True,
            timeout=30,
            text=True
        )

        stdout = (result.stdout or '').strip()
        stderr = (result.stderr or '').strip()
        output = stdout + ("\n" + stderr if stderr else "")

        logging.info(
            'create-account %s => rc=%s output=%s',
            name,
            result.returncode,
            output.replace('\n', ' | ')
        )

        # Success
        if result.returncode == 0 or 'SUCCESS' in output:
            return jsonify({
                'success': True,
                'message': f'Account \"{name}\" created successfully!'
            })

        # Failure
        return jsonify({'error': output or 'Account creation failed'}), 400

    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Connection timeout - server may be offline'}), 500

    except Exception as e:
        app.logger.exception('Account creation exception')
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

if __name__ == '__main__':
    # Public-facing account creation API
    app.run(host='0.0.0.0', port=9080, debug=False)

