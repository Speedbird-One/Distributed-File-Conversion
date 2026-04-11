import subprocess
import os

VENV_ACTIVATE = os.path.abspath(r".\.venv\Scripts\Activate.ps1")

SCRIPTS = {"Worker": "worker.py", "Master": "master.py"}


def launch_backend():
    base_path = os.getcwd()
    tab_commands = []
    titles = list(SCRIPTS.keys())

    for title, file in SCRIPTS.items():
        file_path = os.path.abspath(file)

        if not os.path.exists(file_path):
            print(f"Warning: {file} not found. Skipping...")
            continue

        pwsh_cmd = f"pwsh -NoExit -Command \"$Host.UI.RawUI.WindowTitle = '{title}' \; & '{VENV_ACTIVATE}' \; python '{file_path}'\""
        tab_commands.append(pwsh_cmd)

    if not tab_commands:
        print("No valid scripts found.")
        return

    full_cmd = f'wt -d "{base_path}" --title "{titles[0]}" {tab_commands[0]}'

    if len(tab_commands) > 1:
        full_cmd += (
            f' ; new-tab -d "{base_path}" --title "{titles[1]}" {tab_commands[1]}'
        )

    subprocess.Popen(full_cmd, shell=True)
    print(f"Launching {', '.join(titles)}...")


if __name__ == "__main__":
    launch_backend()
