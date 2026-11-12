"""Download the UNSW-NB15 official training partition from a public mirror (Hugging Face dataset Mouwiya/UNSW-NB15).
Official source: https://research.unsw.edu.au/projects/unsw-nb15-dataset (free for academic use; cite Moustafa & Slay, 2015).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import urllib.request

URL = "https://huggingface.co/datasets/Mouwiya/UNSW-NB15/resolve/main/UNSW_NB15_training-set.csv"
DEST = os.path.join("data", "raw", "unsw-nb15", "UNSW_NB15_training-set.csv")

if __name__ == "__main__":
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.exists(DEST):
        print("already present:", DEST)
    else:
        print("downloading ...")
        urllib.request.urlretrieve(URL, DEST)
        print("saved", DEST)
