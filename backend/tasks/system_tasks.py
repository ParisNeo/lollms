# backend/tasks/system_tasks.py
import os
import zipfile
import shutil
import json
import socket
import ipaddress
import datetime
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import desc
from backend.config import PROJECT_ROOT, APP_DATA_DIR
from backend.task_manager import Task
from backend.db.models.db_task import DBTask
from backend.db.models.config import GlobalConfig
from backend.session import get_user_lollms_client
from backend.ws_manager import manager
from backend.settings import settings

def _create_backup_task(task: Task, password: str):
    """
    Creates an AES-encrypted zip archive of the application folder using pyzipper.
    Requires 'pyzipper' to be installed.
    """
    try:
        import pyzipper
    except ImportError:
        task.log("Critical Error: 'pyzipper' module not found. Please run 'pip install pyzipper' to enable password-protected backups.", "CRITICAL")
        raise ImportError("pyzipper module is required for secure backups.")

    if not password:
        task.log("Backup failed: Password is mandatory for system dumping.", "ERROR")
        raise ValueError("Password is required.")

    task.log("Starting secure application backup.")
    
    backup_dir = APP_DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"lollms_backup_{timestamp}.zip"
    backup_filepath = backup_dir / backup_filename

    # Exclude common large/unnecessary folders
    exclusions = {
        '.git', '.venv', 'venv', '__pycache__', 'node_modules', 
        '.vscode', '.idea', '.DS_Store',
        str(backup_dir.relative_to(PROJECT_ROOT)) # Exclude the backup dir itself
    }
    
    # Also exclude common cache/temp file patterns
    exclude_patterns = ['*.pyc', '*.log', '*.tmp', '*.db-journal', '*.lock']

    try:
        total_files_to_zip = 0
        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in exclusions]
            total_files_to_zip += len(files)

        files_zipped = 0

        # Create AES encrypted zip
        with pyzipper.AESZipFile(backup_filepath, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
            zf.setpassword(password.encode('utf-8'))
            zf.setencryption(pyzipper.WZ_AES, nbits=256) # Strong 256-bit AES

            for root, dirs, files in os.walk(PROJECT_ROOT):
                dirs[:] = [d for d in dirs if d not in exclusions]

                for file in files:
                    if task.cancellation_event.is_set():
                        task.log("Backup cancelled.", "WARNING")
                        return {"message": "Backup cancelled by user."}

                    file_path = Path(root) / file
                    try:
                        arcname = file_path.relative_to(PROJECT_ROOT)
                    except ValueError:
                        continue
                    
                    if any(part in exclusions for part in arcname.parts): continue
                    if any(file_path.match(p) for p in exclude_patterns): continue

                    try:
                        zf.write(file_path, arcname)
                    except Exception as e:
                        task.log(f"Skipped file {file}: {e}", "WARNING")

                    files_zipped += 1
                    if total_files_to_zip > 0 and files_zipped % 50 == 0:
                        progress = int(100 * files_zipped / total_files_to_zip)
                        task.set_progress(progress)
        
        task.set_progress(100)
        task.log(f"Secure backup created successfully: {backup_filename}")
        
        return {"filename": backup_filename, "message": "Secure backup complete."}

    except Exception as e:
        task.log(f"Backup failed: {e}", "CRITICAL")
        if backup_filepath.exists():
            try:
                os.remove(backup_filepath)
            except:
                pass
        raise

def _analyze_logs_task(task: Task, username: str):
    """
    Analyzes recent system tasks (failed/errors) using the user's default LLM.
    """
    task.log("Starting system log analysis.")
    task.set_progress(10)

    # 1. Gather recent problematic logs from the DB
    logs_summary = []
    with task.db_session_factory() as db:
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        
        # Fetch tasks with errors or failures in the last 24h
        problematic_tasks = db.query(DBTask).filter(
            DBTask.created_at >= yesterday,
            DBTask.status.in_(['failed', 'cancelled'])
        ).order_by(desc(DBTask.created_at)).limit(20).all()

        if not problematic_tasks:
            logs_summary.append("No failed or cancelled tasks found in the last 24 hours.")
        else:
            for pt in problematic_tasks:
                logs_summary.append(f"- Task '{pt.name}' (ID: {pt.id}) Status: {pt.status}")
                if pt.error:
                    logs_summary.append(f"  Error: {pt.error[:300]}...") # Truncate error
                if pt.logs:
                    # Get last 2 logs
                    recent_logs = pt.logs[-2:] if len(pt.logs) > 2 else pt.logs
                    for l in recent_logs:
                        logs_summary.append(f"  Log: [{l.get('level', 'INFO')}] {l.get('message', '')}")

    logs_text = "\n".join(logs_summary)
    
    task.set_progress(30)
    task.log("Logs gathered. Generating analysis with LLM...")

    try:
        lc = get_user_lollms_client(username)
        
        prompt = f"""You are a System Administrator AI. Analyze the following summary of recent system tasks and errors (last 24h).
Provide a concise markdown report identifying:
1. Critical failures.
2. Potential root causes.
3. Recommended actions.

If there are no errors, just state that the system appears healthy.

--- LOG DATA ---
{logs_text}
--- END LOG DATA ---
"""
        response = lc.generate_text(prompt)
        
        task.set_progress(100)
        task.log("Analysis complete.")
        return {"report": response, "generated_at": datetime.now().isoformat()}

    except Exception as e:
        task.log(f"Analysis failed: {e}", "ERROR")
        raise e

def _generate_self_signed_cert_task(task: Task):
    """Generates a self-signed certificate and private key, saves them, and updates settings."""
    task.log("Starting self-signed certificate generation.")
    
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        error_msg = "cryptography library is required. Please install it: pip install cryptography"
        task.log(error_msg, "CRITICAL")
        raise ImportError(error_msg)

    task.set_progress(10)
    certs_dir = APP_DATA_DIR / "certificates"
    certs_dir.mkdir(exist_ok=True, parents=True)
    
    key_path = certs_dir / "lollms_key.pem"
    cert_path = certs_dir / "lollms_cert.pem"

    task.log("Generating 2048-bit RSA private key...")
    # Generate Private Key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    task.set_progress(30)

    # Generate Certificate
    hostname = socket.gethostname()
    task.log(f"Building certificate for hostname: {hostname}")
    
    # Subject/Issuer
    subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"FR"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Ile-de-France"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Paris"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"LoLLMs"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
    ])

    # SANs
    alt_names = [
        x509.DNSName(u"localhost"),
        x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
        x509.DNSName(hostname)
    ]
    try:
        local_ip = socket.gethostbyname(hostname)
        alt_names.append(x509.IPAddress(ipaddress.ip_address(local_ip)))
    except:
        pass

    # Builder
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        subject # Self-signed
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        # Valid for 10 years
        datetime.utcnow() + timedelta(days=3650)
    ).add_extension(
        x509.SubjectAlternativeName(alt_names),
        critical=False,
    ).sign(key, hashes.SHA256())
    
    task.set_progress(60)
    task.log("Saving certificate files...")

    # Write Key
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        
    # Write Cert
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    key_abs = str(key_path.resolve())
    cert_abs = str(cert_path.resolve())

    task.set_progress(80)
    task.log("Updating system configuration...")

    # Update DB
    with task.db_session_factory() as db:
        updates = {
            "ssl_keyfile": key_abs,
            "ssl_certfile": cert_abs,
            "https_enabled": True
        }
        
        all_db_configs = {c.key: c for c in db.query(GlobalConfig).all()}
        
        for k, v in updates.items():
            db_config = all_db_configs.get(k)
            if db_config:
                orig_val = db_config.value
                type_val = "string"
                if k == "https_enabled": type_val = "boolean"
                
                # Preserve existing structure if possible
                if isinstance(orig_val, dict):
                    db_config.value = json.dumps({"value": v, "type": type_val})
                else:
                    # Try load
                    try:
                        loaded = json.loads(orig_val)
                        if isinstance(loaded, dict) and 'type' in loaded:
                            loaded['value'] = v
                            db_config.value = json.dumps(loaded)
                        else:
                            db_config.value = json.dumps({"value": v, "type": type_val})
                    except:
                        db_config.value = json.dumps({"value": v, "type": type_val})
        db.commit()
        
        # Trigger reload on workers if possible, or frontend refresh
        # We broadcast a general update
        try:
            settings.refresh(db)
            # manager import might cause circular dependency if at top level, but inside func is ok if imported
            manager.broadcast_sync({"type": "settings_updated"})
        except Exception as e:
            task.log(f"Warning: Could not broadcast settings update: {e}", "WARNING")

    task.set_progress(100)
    task.log("Certificate generation complete. HTTPS enabled.")

    return {
        "message": "Certificate generated and applied.",
        "cert_path": cert_abs,
        "key_path": key_abs
    }
