# This file allow that the agent create charts using matplotlib. The agent can use this tool to create charts that can help it analyze the data and answer questions about it.

import matplotlib.pyplot as plt

def plot_top_products(series):
    """
    Generate a bar chart for top products.
    """
    series.plot(kind="bar")

    plt.title("Top Products")
    plt.xlabel("Product")
    plt.ylabel("Quantity Sold")

    plt.tight_layout()

    plt.savefig("top_products_chart.png")

    return "top_products_chart.png"


def plot_sales_by_country(series):
    """
    Generate a bar chart for sales by country.
    """
    series.plot(kind="bar")

    plt.title("Sales by Country")
    plt.xlabel("Country")
    plt.ylabel("Quantity Sold")

    plt.tight_layout()

    plt.savefig("sales_by_country_chart.png")

    return "sales_by_country_chart.png"


def plot_monthly_sales(series):
    """
    Generate a line chart for monthly sales.
    """
    series.plot(kind="line")

    plt.title("Monthly Sales")
    plt.xlabel("Month")
    plt.ylabel("Quantity Sold")

    plt.tight_layout()

    plt.savefig("monthly_sales_chart.png")

    return "monthly_sales_chart.png"

