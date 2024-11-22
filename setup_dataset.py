import subprocess
import sys
import argparse

def run_script(script_name, args=None):
    try:
        cmd = [sys.executable, script_name]
        if args:
            cmd.extend(args)
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError as e:
        print(f"Error running {script_name}: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Setup dataset by running all preprocessing scripts.")
    parser.add_argument(
        '--max_files',
        type=int,
        default=10,
        help='Maximum number of files to process in fda-downloader.py and data-normalizer.py (default: 10)'
    )
    args = parser.parse_args()

    scripts = [
        ("fda-downloader.py", ["--max_files", str(args.max_files)]),
        ("data-normalizer.py", ["--max_files", str(args.max_files)]),
        ("graph-preprocessing.py", None),
    ]
    
    for script, script_args in scripts:
        if script_args:
            args_str = " ".join(script_args)
            print(f"Running {script} with arguments: {args_str}...")
        else:
            print(f"Running {script}...")
        run_script(script, script_args)
    print("Dataset setup complete.")

if __name__ == "__main__":
    main()