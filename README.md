# Zizzys TW404 Account and Admin Web Services

Lightweight Flask applications for managing TW404 game server accounts and administration. Provides account creation endpoints and a web-based admin dashboard for server control via SSH to Solaris backend.

## Features

- **Account Creation Service** (`app.py`): RESTful API for creating game accounts
- **Admin Dashboard** (`admin_app.py`): Web interface for server management
- **SSH Integration**: Secure remote execution on Solaris backend
- **Health Checks**: Connectivity verification before operations
- **Logging**: Track all account creation and admin actions

## Architecture

```
Linux (10.0.0.206)
├── app.py (port 9080)    → Flask account creation service
└── admin_app.py (port 8081) → Flask admin dashboard
        ↓ (SSH)
Solaris (192.168.122.35)
├── create-accounts script (uh utility)
├── Game servers (jtales0, jtales1, jtales2)
└── Database (port 45012)
```

## Requirements

- **Python**: 3.7+
- **Flask**: 3.1.2+
- **SSH**: Configured passwordless access to Solaris backend (192.168.122.35 or configured alias)
- **Linux**: Deployment target

See `requirements.txt` for Python dependencies.

## Installation

```bash
pip install -r requirements.txt
```

## Running

### Account Creation Service
```bash
python3 app.py
# Listens on http://localhost:9080
```

### Admin Dashboard
```bash
python3 admin_app.py
# Listens on http://localhost:8081
```

## Configuration

### Environment Variables
- `SOLARIS_HOST`: SSH host for Solaris backend (default: `solaris`)

### SSH Setup
Ensure `~/.ssh/config` contains:
```
Host solaris
    HostName 192.168.122.35
    User root
    StrictHostKeyChecking no
```

### Account Creation Defaults
Edit `app.py` constants:
```python
EMAIL = 'twsrv@localhost'
BIRTHDATE = '19990909'
RNAME = '1'
SOLAR = '4'
GENDER = '5'
```

## API Endpoints

### Account Creation (app.py)
- `GET /`: HTML form
- `POST /api/create`: JSON account creation
- `GET /api/health`: SSH connectivity check

### Admin Dashboard (admin_app.py)
- `GET /`: Admin dashboard UI
- `POST /api/start`: Start game servers
- `POST /api/stop`: Stop game servers
- `GET /api/health`: System health check

## Logging

- **Account Creation**: `/tmp/tw404_accounts.log`
- **Admin Actions**: `/tmp/tw404_admin.log`

## Troubleshooting

### SSH Connection Failed
```bash
# Test SSH to Solaris
ssh solaris "ls /tw404"
# Or specify host directly
SOLARIS_HOST=192.168.122.35 python3 app.py
```

### Port Already in Use
```bash
lsof -i :9080  # Account service
lsof -i :8081  # Admin service
```

## Security Notes

- Ensure `~/.ssh/config` has strict permissions: `chmod 600 ~/.ssh/config`
- Use SSH keypairs, avoid password authentication
- Restrict access to admin endpoints (add authentication as needed)
- Set `ConnectTimeout=3` to fail fast on unreachable Solaris

## See Also

- **Packet Proxy**: https://github.com/wrharper/ZizzysEpolPacketIntercepter
- **Original TW404**: Game server repository
