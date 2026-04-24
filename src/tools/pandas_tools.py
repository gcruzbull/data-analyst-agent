# This module provides utility functions for working with pandas DataFrames.
# This module provides the tools that the agent can use to analyze the data. Each function takes a pandas DataFrame as input and returns a string output that can be used by the agent to answer questions about the data.

import pandas as pd

def top_products(df: pd.DataFrame):
    """
    Returns the top selling products by quantity.
    """
    result = (
        df.groupby("Description")["Quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    return result

def sales_by_country(df: pd.DataFrame):
    """
    Returns total sales by country.
    """
    result = (
        df.groupby("Country")["Quantity"]
        .sum()
        .sort_values(ascending=False)
    )

    return result

def monthly_sales(df: pd.DataFrame):
    """
    Returns sales aggregated by month.
    """
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"])

    result = (
        df.groupby(df["InvoiceDate"].dt.to_period("M"))["Quantity"]
        .sum()
    )

    return result

