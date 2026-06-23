import matplotlib.pyplot as plt

labels = ["TSLA", "GOOGL", "NVDA", "AMD"]

sizes = [894621, 134039, 107665, 70126]

plt.pie(
    sizes,
    labels=labels,
    autopct="%1.1f%%"
)

plt.title("Portfolio Allocation")

plt.show()