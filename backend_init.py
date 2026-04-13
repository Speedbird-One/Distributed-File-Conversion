import subprocess
import os
import platform
import shlex

# Configuration
SCRIPTS = {"Worker": "worker.py", "Master": "master.py"}
VENV_DIR = ".venv"


def get_venv_activate():
    """Returns the platform-specific venv activation command."""
    if platform.system() == "Windows":
        # Windows uses Scripts\Activate.ps1
        return os.path.abspath(os.path.join(VENV_DIR, "Scripts", "Activate.ps1"))
    # Unix-like uses bin/activate
    return os.path.abspath(os.path.join(VENV_DIR, "bin", "activate"))


def launch_backend():
    os_name = platform.system()
    base_path = os.getcwd()
    venv_path = get_venv_activate()

    tasks = []
    for title, file in SCRIPTS.items():
        file_path = os.path.abspath(file)
        if not os.path.exists(file_path):
            print(f"Warning: {file} not found. Skipping...")
            continue
        tasks.append((title, file_path))

    if not tasks:
        print("No valid scripts found.")
        return

    if os_name == "Windows":
        # Build the 'wt' command list to handle paths with spaces safely
        wt_cmd = ["wt", "-d", base_path]

        for i, (title, file_path) in enumerate(tasks):
            if i > 0:
                wt_cmd.append(";")
                wt_cmd.append("new-tab")
                wt_cmd.extend(["-d", base_path])

            # FIX: Added '-ExecutionPolicy Bypass' to allow Activate.ps1 to run.
            # Used '\;' so Windows Terminal doesn't split the tab prematurely.
            ps_logic = f"& '{venv_path}' \; python '{file_path}'"

            wt_cmd.extend(
                [
                    "--title",
                    title,
                    "powershell.exe",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-NoExit",
                    "-Command",
                    ps_logic,
                ]
            )

        # Execute without shell=True to preserve the argument list structure
        subprocess.Popen(wt_cmd)

    elif os_name == "Darwin":  # macOS
        for title, file_path in tasks:
            inner_cmd = (
                f"source {shlex.quote(venv_path)} && python3 {shlex.quote(file_path)}"
            )
            applescript = f'tell application "Terminal" to do script "cd {shlex.quote(base_path)} && {inner_cmd}"'
            subprocess.run(["osascript", "-e", applescript])

    elif os_name == "Linux":
        for title, file_path in tasks:
            inner_cmd = (
                f"source {shlex.quote(venv_path)} && python3 {shlex.quote(file_path)}"
            )
            # Standard for most Linux distributions
            subprocess.Popen(
                [
                    "gnome-terminal",
                    "--tab",
                    "--title",
                    title,
                    "--",
                    "bash",
                    "-c",
                    f"{inner_cmd}; exec bash",
                ]
            )

    print(f"Launching {', '.join(SCRIPTS.keys())} on {os_name}...")


if __name__ == "__main__":
    launch_backend()
