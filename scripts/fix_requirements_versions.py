import importlib.metadata
import re
import sys
from pathlib import Path

def get_installed_version(package_name):
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None

def main():
    # Assume script is in scripts/ folder and requirements.txt is in parent
    project_root = Path(__file__).resolve().parent.parent
    requirements_path = project_root / "requirements.txt"

    if not requirements_path.exists():
        print(f"Error: Could not find requirements.txt at {requirements_path}")
        sys.exit(1)

    print(f"Reading {requirements_path}...")
    with open(requirements_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    
    # Regex to capture the package name. 
    # It stops before comparison operators, whitespace, or comment #.
    # Package names can contain letters, numbers, ., -, _
    # Extras are in [], e.g. package[extra]
    # We want to preserve 'package[extra]' but replace the version part.
    
    name_pattern = re.compile(r"^([a-zA-Z0-9_\-\.]+(?:\[[a-zA-Z0-9_\-\.,]+\])?)")

    for line in lines:
        original_line = line
        stripped = line.strip()
        
        # Skip empty lines and comments
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue

        # Skip links/editable installs which might be URLs or local paths
        if stripped.startswith("-e") or "://" in stripped:
            new_lines.append(line)
            continue

        match = name_pattern.match(stripped)
        if match:
            full_package_ref = match.group(1) # e.g. "pandas" or "uvicorn[standard]"
            
            # Extract clean package name for lookup (remove extras)
            clean_name = full_package_ref.split('[')[0]
            
            # Normalize name for lookup (importlib usually handles mixed case, but standard is lowercase)
            # We keep original casing for the file write though.
            
            installed_version = get_installed_version(clean_name)
            
            if installed_version:
                # Create new line with pinned version
                new_line = f"{full_package_ref}=={installed_version}\n"
                new_lines.append(new_line)
                # Check if it actually changed
                # We compare stripped versions to avoid newline differences confusing the logic
                if new_line.strip() != stripped:
                    print(f"Pinned: {clean_name} -> {installed_version}")
            else:
                print(f"Warning: Package '{clean_name}' not found in current environment. Keeping original entry.")
                new_lines.append(line)
        else:
            # Could not parse package name, keep line as is
            new_lines.append(line)

    print(f"Writing updates to {requirements_path}...")
    with open(requirements_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print("Done.")

if __name__ == "__main__":
    main()
