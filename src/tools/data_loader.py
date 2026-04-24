# Allow upload of CSV files and load them into a pandas DataFrame for analysis.

import pandas as pd
import os

#BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
#DATA_PATH = os.path.join(BASE_DIR, "data", "dataset_clean.csv")

#def load_data() -> pd.DataFrame:
#    """
#    Load cleaned dataset
#    """
#    df = pd.read_csv(DATA_PATH)
#    return df

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_PATH = BASE_DIR / "data" / "dataset_clean.csv"

def load_data():
    print("Loading from:", DATA_PATH)  # debug
    return pd.read_csv(DATA_PATH)

print("BASE_DIR:", BASE_DIR)
print("DATA_PATH:", DATA_PATH)

