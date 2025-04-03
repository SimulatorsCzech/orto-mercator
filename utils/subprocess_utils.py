import subprocess
import logging
from typing import List, Tuple

# Configure logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    # Configure log handler only once (streaming to stdout)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def run_command(cmd: List[str]) -> Tuple[str, str]:
    """
    Spustí zadaný příkaz v podprocesu, počká na dokončení a vrátí stdout a stderr.
    Pokud příkaz skončí s nenulovým návratovým kódem, vyvolá výjimku.
    """
    logger.info("Executing command: " + " ".join(cmd))
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        logger.error(f"Command '{' '.join(cmd)}' failed: {stderr}")
        raise Exception(f"Command '{' '.join(cmd)}' failed: {stderr}")
    logger.info("Command executed successfully. Output: " + stdout.strip())
    return stdout, stderr
