# This module provides tools for anomaly detection in sales data using Machine Learning techniques. 
# The agent can use this tool to identify unusual patterns in the sales data that may indicate issues or opportunities for further analysis.

import pandas as pd
from sklearn.ensemble import IsolationForest

def detect_sales_anomalies(df: pd.DataFrame):
    """
    Detect anomalies in sales quantity using Isolation Forest.
    """
    model = IsolationForest(
        n_estimators=100,
        contamination=0.01,
        random_state=42
    )

    X = df[["Quantity"]]

    df["anomaly"] = model.fit_predict(X)

    anomalies = df[df["anomaly"] == -1]

    return anomalies

