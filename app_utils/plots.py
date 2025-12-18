import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="darkgrid")

def clean_axes(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.2)
    ax.tick_params(labelsize=9)

def line_plot(df, x, y, title, ylabel):
    fig, ax = plt.subplots(figsize=(8, 3.5), dpi=150)
    sns.lineplot(data=df, x=x, y=y, marker="o", ax=ax)
    ax.set_title(title, fontsize=12)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("")
    clean_axes(ax)
    fig.tight_layout()
    return fig
