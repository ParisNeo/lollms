# lollms/scripts/setup_wizard.py
import os
import platform
import subprocess
import sys
from pathlib import Path

# Setup PYTHONPATH to allow imports from backend
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from backend.db.session import SessionLocal, init_database, engine as db_engine
    from backend.db.base import Base
    from backend.db.models.config import LLMBinding, TTIBinding, TTSBinding
    from backend.db.models.user import User
    from backend.security import get_password_hash
    from backend.config import INITIAL_ADMIN_USER_CONFIG, APP_DB_URL
except ImportError as e:
    print("\n[ERROR] Failed to import necessary modules.")
    print(f"Details: {e}")
    print("Please ensure you are running this script from the project's root directory or that the PYTHONPATH is set correctly.")
    sys.exit(1)

class ASCIIColors:
    @staticmethod
    def red(text): return f"\033[91m{text}\033[0m"
    @staticmethod
    def green(text): return f"\033[92m{text}\033[0m"
    @staticmethod
    def yellow(text): return f"\033[93m{text}\033[0m"
    @staticmethod
    def blue(text): return f"\033[94m{text}\033[0m"
    @staticmethod
    def magenta(text): return f"\033[95m{text}\033[0m"
    @staticmethod
    def cyan(text): return f"\033[96m{text}\033[0m"

def print_header(text):
    print(f"\n{ASCIIColors.magenta('--- ' + text + ' ---')}")

def get_db_session():
    init_database(APP_DB_URL)
    Base.metadata.create_all(bind=db_engine)
    return SessionLocal()

def check_command(command):
    try:
        subprocess.run([command, '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_or_install_ollama():
    print_header("Checking for Ollama")
    if check_command('ollama'):
        print(ASCIIColors.green("Ollama is already installed."))
        return True

    print(ASCIIColors.yellow("Ollama is not installed or not in your PATH."))
    system = platform.system()
    
    if system == "Linux":
        install = input("Would you like to try installing it now? (y/N): ").lower()
        if install == 'y':
            try:
                print("Running Ollama installation script for Linux...")
                subprocess.run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=True)
                print(ASCIIColors.green("Ollama installed successfully."))
                print("Please ensure the Ollama service is running. You might need to start it manually:")
                print(ASCIIColors.cyan("  systemctl --user start ollama"))
                print(ASCIIColors.cyan("  systemctl --user enable --now ollama"))
                return True
            except subprocess.CalledProcessError as e:
                print(ASCIIColors.red(f"Ollama installation script failed: {e}"))
                return False
    elif system == "Darwin": # macOS
        print("Please download and install Ollama for macOS from:")
        print(ASCIIColors.cyan("  https://ollama.com/download/mac"))
    elif system == "Windows":
        print("Please download and install Ollama for Windows from:")
        print(ASCIIColors.cyan("  https://ollama.com/download/windows"))

    input(ASCIIColors.yellow("\nPress Enter to continue after you have installed and started Ollama..."))
    
    if check_command('ollama'):
        print(ASCIIColors.green("Ollama is now detected."))
        return True
    else:
        print(ASCIIColors.red("Ollama still not detected. Please ensure it is installed and in your system's PATH."))
        return False

def pull_ollama_model(model_name):
    print(f"Pulling model '{model_name}'. This may take some time...")
    try:
        process = subprocess.Popen(['ollama', 'pull', model_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"\r{output.strip()}", end="")
        print() # Newline after progress
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        print(ASCIIColors.green(f"Model '{model_name}' pulled successfully."))
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(ASCIIColors.red(f"Failed to pull model '{model_name}': {e}"))
        print("Please make sure Ollama is running and accessible.")
        return False

def create_admin_if_not_exists(db):
    if db.query(User).count() > 0:
        return db.query(User).filter(User.is_admin == True).first() or db.query(User).first()

    print("Creating default administrator account...")
    admin_username = INITIAL_ADMIN_USER_CONFIG.get("username", "admin")
    admin_password = INITIAL_ADMIN_USER_CONFIG.get("password", "admin")
    
    new_admin = User(
        username=admin_username,
        hashed_password=get_password_hash(admin_password),
        is_admin=True,
        is_active=True
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    print(ASCIIColors.green(f"Admin user '{admin_username}' created with password '{admin_password}'. Please change this password later."))
    return new_admin

def get_or_create_binding(db, model_class, alias, name, config):
    binding = db.query(model_class).filter(model_class.alias == alias).first()
    if binding:
        print(f"{model_class.__name__} binding '{alias}' already exists.")
        return binding
    
    print(f"Creating {model_class.__name__} binding '{alias}'...")
    new_binding = model_class(alias=alias, name=name, config=config, is_active=True)
    db.add(new_binding)
    db.commit()
    db.refresh(new_binding)
    print(ASCIIColors.green(f"{model_class.__name__} binding created."))
    return new_binding

def main_wizard():
    print(ASCIIColors.cyan("".join(["="*60, "\n", " "*(20), "LoLLMs Setup Wizard\n", "="*60])))
    print("Welcome! This wizard will help you with the initial setup.")

    while True:
        print("\nPlease choose an installation profile:")
        print(ASCIIColors.yellow("  1.") + " Continue without setup (manual configuration)")
        print(ASCIIColors.yellow("  2.") + " Simple LLM configuration (Ollama)")
        print(ASCIIColors.yellow("  3.") + " LLM with image input (Ollama Multimodal)")
        print(ASCIIColors.yellow("  4.") + " LLM with image input/output (Ollama + Diffusers)")
        print(ASCIIColors.yellow("  5.") + " LLM with image I/O and Text-to-Speech (Ollama + Diffusers + XTTS)")
        
        choice = input(f"Enter your choice (1-5): ").strip()

        if choice in ['1', '2', '3', '4', '5']:
            break
        else:
            print(ASCIIColors.red("Invalid choice. Please enter a number between 1 and 5."))

    db = get_db_session()
    
    try:
        if choice == '1':
            print("Proceeding with manual setup. You can configure everything from the UI.")
            sys.exit(0)

        if not get_or_install_ollama():
            raise RuntimeError("Ollama installation is required for this profile.")

        admin_user = create_admin_if_not_exists(db)
        get_or_create_binding(db, LLMBinding, "ollama", "ollama", {"host_address": "http://localhost:11434"})

        model_to_pull = None
        if choice == '2':
            print_header("Simple LLM Configuration")
            models = {'1': ('Mistral (7B)', 'mistral:7b'), '2': ('Llama 3 (8B)', 'llama3:8b'), '3': ('Gemma (2B)', 'gemma:2b')}
            print("Select a small model to download:")
            for k, v in models.items(): print(f"  {k}. {v[0]}")
            model_choice = input(f"Enter your choice (1-{len(models)}): ").strip()
            model_to_pull = models.get(model_choice, ('Mistral (7B)', 'mistral:7b'))[1]
        
        if choice in ['3', '4', '5']:
            print_header("LLM with Image Input")
            models = {'1': ('LLaVA (7B)', 'llava:7b'), '2': ('Moondream 2', 'moondream:latest')}
            print("Select a multimodal model to download:")
            for k, v in models.items(): print(f"  {k}. {v[0]}")
            model_choice = input(f"Enter your choice (1-{len(models)}): ").strip()
            model_to_pull = models.get(model_choice, ('LLaVA (7B)', 'llava:7b'))[1]

        if model_to_pull:
            if pull_ollama_model(model_to_pull):
                admin_user.lollms_model_name = f"ollama/{model_to_pull}"
                print(ASCIIColors.green(f"Set '{model_to_pull}' as default for admin."))

        if choice in ['4', '5']:
            print_header("Image Generation (TTI)")
            get_or_create_binding(db, TTIBinding, "diffusers", "diffusers", {"lollms_diffusers_base_url": "http://localhost:9601"})
            admin_user.tti_binding_model_name = "diffusers/dreamshaper-8"
            print(ASCIIColors.green("Configured 'diffusers' for image generation with 'dreamshaper-8'."))
            print(ASCIIColors.yellow("Note: The diffusers server will be installed automatically on its first use from the UI."))

        if choice == '5':
            print_header("Text-to-Speech (TTS)")
            get_or_create_binding(db, TTSBinding, "xtts", "xtts", {"lollms_xtts_base_url": "http://localhost:9602"})
            print(ASCIIColors.green("Configured 'xtts' for text-to-speech."))
            print(ASCIIColors.yellow("Note: The XTTS server will be installed automatically on its first use from the UI."))

        db.commit()

    except Exception as e:
        print(ASCIIColors.red(f"\nAn error occurred during setup: {e}"))
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
    
    print(ASCIIColors.green("\nSetup completed successfully! The application will now start."))
    sys.exit(0)

if __name__ == "__main__":
    main_wizard()