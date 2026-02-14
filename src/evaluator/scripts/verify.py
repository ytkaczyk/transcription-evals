import subprocess
import sys
import os


def run_command(command, description):
    print(f"\n--- Running {description} ---")
    try:
        # Run the command and stream output to stdout
        subprocess.check_call(command)
        print(f"✅ {description} passed.")
    except subprocess.CalledProcessError:
        print(f"❌ {description} failed.")
        sys.exit(1)


def main():
    # Ensure we are in the project root (one level up from this script)
    # This allows running 'uv run scripts/verify.py' from src/evaluator
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)

    # 1. Run Pytest
    run_command(["uv", "run", "pytest"], "pytest")

    # 2. Run Pylint
    # We target the current directory packages
    # Using the flags recommended in instructions: --disable=C0301 (line too long)
    run_command(["uv", "run", "pylint", "--disable=C0301",
                "transcribers", "evaluator.py", "main.py", "tests"], "pylint")

    # 3. Run Pyright
    run_command(["uv", "run", "pyright", "."], "pyright")

    print("\n🎉 All checks passed!")


if __name__ == "__main__":
    main()
