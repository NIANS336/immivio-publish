import argparse
import logging
from pathlib import Path
from .config import Config
from .server import run

parser = argparse.ArgumentParser(description="Immivio LAN AI subtitles")
parser.add_argument("--config", required=True, help="Private JSON configuration")
args = parser.parse_args()
logs = Path(args.config).resolve().parent / "logs"
logs.mkdir(exist_ok=True)
logging.basicConfig(filename=logs / "service.log", level=logging.WARNING,
                    format="%(asctime)s %(levelname)s %(message)s")
run(Config.load(args.config))
