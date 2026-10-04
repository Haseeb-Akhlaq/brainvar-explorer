"""
Run the ACTUAL per_gene_cpm_brainvar.py unmodified and capture exactly what it
draws, by intercepting the matplotlib calls it makes.

Nothing about the script is reimplemented here — it is executed as-is via
runpy, with sys.argv set as if run from the command line.
"""
import json, pathlib, runpy, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SCRIPT = str(pathlib.Path(__file__).resolve().parent.parent / "data" / "per_gene_cpm_brainvar.py")

def capture(symbol):
    grabbed = {"plots": [], "band": None}

    real_plot = plt.plot
    real_fill = plt.fill_between
    real_save = plt.savefig

    def spy_plot(*args, **kwargs):
        # The script calls plt.plot(x, y, 'o', ...) then plt.plot(x, lowess, ...)
        if len(args) >= 2 and hasattr(args[0], "__len__"):
            grabbed["plots"].append((list(args[0]), list(args[1]), kwargs.get("color")))
        return real_plot(*args, **kwargs)

    def spy_fill(x, lo, hi, *a, **k):
        grabbed["band"] = (list(x), list(lo), list(hi))
        return real_fill(x, lo, hi, *a, **k)

    plt.plot, plt.fill_between, plt.savefig = spy_plot, spy_fill, lambda *a, **k: None
    old_argv = sys.argv
    try:
        sys.argv = [SCRIPT, symbol]
        runpy.run_path(SCRIPT, run_name="__main__")
    finally:
        sys.argv = old_argv
        plt.plot, plt.fill_between, plt.savefig = real_plot, real_fill, real_save
        plt.close("all")

    scatter = next(p for p in grabbed["plots"] if p[2] == "red")
    curve = next(p for p in grabbed["plots"] if p[2] == "royalblue")
    return {
        "x": scatter[0], "y": scatter[1],
        "curve_x": curve[0], "curve_y": curve[1],
        "band_x": grabbed["band"][0], "lower": grabbed["band"][1], "upper": grabbed["band"][2],
    }

if __name__ == "__main__":
    out = {}
    for sym in sys.argv[1:]:
        out[sym] = capture(sym)
        print(f"captured {sym}: {len(out[sym]['x'])} points, {len(out[sym]['curve_y'])} curve values",
              file=sys.stderr)
    with open(str(pathlib.Path(__file__).parent / "script_output.json"), "w") as f:
        json.dump(out, f)
    print("written", file=sys.stderr)
