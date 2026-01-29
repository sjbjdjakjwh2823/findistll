from run_crypto_engine import run_history_mode
import logging

# Set logging to see output
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("FORCE TRIGGER: History Mode (2000-Present)")
    run_history_mode()
