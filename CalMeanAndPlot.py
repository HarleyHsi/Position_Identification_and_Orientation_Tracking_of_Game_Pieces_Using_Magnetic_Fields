import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Configuration ─────────────────────────────────────────────────────────────

CSV_FILES = [
    "sensor_0_10Min0.5Hz.csv",
    "sensor_1_10Min0.5Hz.csv",
    "sensor_2_10Min0.5Hz.csv",
    "sensor_3_10Min0.5Hz.csv",
]

COLUMNS = [
    "timestamp",
    "sensor_id",
    "x_raw", "y_raw", "z_raw",
    "x_cal", "y_cal", "z_cal",
]


MODE = "cal"   # change to "raw" to analyse raw values

AXES   = ["x", "y", "z"]
LABELS = {"x": "Bx", "y": "By", "z": "Bz"}
COLORS = {"x": "#4C72B0", "y": "#DD8452", "z": "#55A868"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_sensor(filepath: str) -> pd.DataFrame:
    """Load a single sensor CSV into a DataFrame."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    df = pd.read_csv(
        filepath,
        header=None,
        names=COLUMNS,
        parse_dates=["timestamp"],
        date_format="%Y-%m-%d %H:%M:%S.%f",
    )

    # Cast numeric columns explicitly (guards against stray text rows)
    numeric_cols = [c for c in COLUMNS if c not in ("timestamp", "sensor_id")]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    df.dropna(subset=numeric_cols, inplace=True)

    return df


def compute_stats(df: pd.DataFrame, mode: str = "cal") -> dict:
    """Return a dict with mean, std, min and max for each axis."""
    stats = {}
    for axis in AXES:
        col  = f"{axis}_{mode}"
        data = df[col].dropna()
        label = LABELS[axis]
        stats[label] = {
            "mean":  data.mean(),
            "std":   data.std(ddof=1),
            "min":   data.min(),
            "max":   data.max(),
            "data":  data,       
        }
    return stats


def print_stats(sensor_id, stats: dict) -> None:
    """Pretty-print the statistics table for one sensor."""
    print(f"\n{'='*55}")
    print(f"  Sensor {sensor_id}")
    print(f"{'='*55}")
    header = f"  {'Axis':<6} {'Mean':>12} {'StdDev':>12} {'Min':>12} {'Max':>12}"
    print(header)
    print(f"  {'-'*53}")
    for label, s in stats.items():
        print(
            f"  {label:<6} "
            f"{s['mean']:>12.4f} "
            f"{s['std']:>12.4f} "
            f"{s['min']:>12.4f} "
            f"{s['max']:>12.4f}"
        )
    print(f"{'='*55}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    all_stats   = {}   
    sensor_dfs  = {}   

    # ── 1. Load & analyse ────────────────────────────────────────────────────
    for filepath in CSV_FILES:
        df        = load_sensor(filepath)
        sid       = df["sensor_id"].iloc[0]       
        stats     = compute_stats(df, mode=MODE)

        all_stats[filepath]  = (sid, stats)
        sensor_dfs[filepath] = df

        print_stats(sid, stats)

    # ── 2. Plot: one figure per sensor ────────────────
    for filepath, (sid, stats) in all_stats.items():

        fig = plt.figure(figsize=(14, 4))
        fig.suptitle(f"Sensor {sid}  —  {filepath}", fontsize=13, fontweight="bold")

        gs = gridspec.GridSpec(1, 3, figure=fig, wspace=0.35)

        for col_idx, label in enumerate(LABELS.values()):
            ax    = fig.add_subplot(gs[0, col_idx])
            s     = stats[label]
            color = COLORS[AXES[col_idx]]
            n     = len(s["data"])


            bins = max(10, int(np.ceil(np.log2(n) + 1)))

            ax.hist(s["data"], bins=bins, color=color, edgecolor="white",
                    linewidth=0.6, alpha=0.85)


            ax.axvline(s["mean"],            color="black", linewidth=1.5,
                       linestyle="--",  label=f"μ = {s['mean']:.3f}")
            ax.axvline(s["mean"] - s["std"], color="grey",  linewidth=1.0,
                       linestyle=":",   label=f"σ = {s['std']:.3f}")
            ax.axvline(s["mean"] + s["std"], color="grey",  linewidth=1.0,
                       linestyle=":")

            ax.set_title(label, fontsize=11)
            ax.set_xlabel("Value", fontsize=9)
            ax.set_ylabel("Count" if col_idx == 0 else "", fontsize=9)
            ax.legend(fontsize=8, loc="upper right")
            ax.tick_params(labelsize=8)

        plt.savefig(f"sensor_{sid}_histograms.png", dpi=150, bbox_inches="tight")
        plt.show()

    # ── 3. Summary comparison across sensors ─────────────────────────────────
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("Mean ± StdDev comparison — all sensors", fontsize=13,
                 fontweight="bold")

    for col_idx, label in enumerate(LABELS.values()):
        ax = axes[col_idx]

        sensor_labels = []
        means, stds   = [], []

        for filepath, (sid, stats) in all_stats.items():
            sensor_labels.append(f"S{sid}")
            means.append(stats[label]["mean"])
            stds.append(stats[label]["std"])

        x = np.arange(len(sensor_labels))
        ax.bar(x, means, yerr=stds, capsize=5,
               color="#4C72B0", edgecolor="white", alpha=0.8, width=0.5,
               error_kw={"elinewidth": 1.5, "ecolor": "black"})

        ax.set_title(label, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(sensor_labels, fontsize=9)
        ax.set_ylabel("Value", fontsize=9)
        ax.tick_params(labelsize=8)
        ax.axhline(0, color="black", linewidth=0.8, linestyle="--")

    plt.tight_layout()
    plt.savefig("all_sensors_comparison.png", dpi=150, bbox_inches="tight")
    plt.show()


if __name__ == "__main__":
    main()
