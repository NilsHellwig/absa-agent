import subprocess
import sys
import os

# Top 20 America Cities (Corrected Population-based List)
CITIES = [
     "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "Jacksonville",
    "Fort Worth", "San Jose", "Austin", "Charlotte", "Columbus",
    "Indianapolis", "San Francisco", "Seattle", "Denver", "Oklahoma City"
]

def run_experiment(city):
    """Runs the absa_agent.py script for a specific city."""
    print(f"\n{'='*50}")
    print(f"RUNNING EXPERIMENT FOR: {city}")
    print(f"{'='*50}\n")
    
    # Define the topic
    topic = f"Restaurants in {city}"
    
    # Generate session ID
    session_id = f"restaurants_{city.lower().replace(' ', '_')}"
    
    # Define the command
    # Using sys.executable to ensure we use the same environment
    cmd = [
        sys.executable, 
        "absa_agent.py", 
        topic,
        "--id", session_id,
        "--max_reviews", "50",  # 50 reviews per experiment
        "--language", "en",      # Explicitly English
        "--forbidden_urls", "opentable.com"
    ]
    
    try:
        # Run the process and wait for completion
        # Using subprocess.run to keep each experiment isolated
        result = subprocess.run(cmd, check=True)
        print(f"\n[SUCCESS] Completed experiment for {city}")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Experiment for {city} failed with exit code {e.returncode}")
    except Exception as e:
        print(f"\n[FATAL] An unexpected error occurred: {e}")

def main():
    if not os.path.exists("absa_agent.py"):
        print("Error: absa_agent.py not found in the current directory.")
        sys.exit(1)
        
    print(f"Starting experiments for {len(CITIES)} cities...")
    
    for city in CITIES:
        run_experiment(city)
        
    print("\nAll experiments completed.")

if __name__ == "__main__":
    main()
