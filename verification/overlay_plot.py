"""Overlay: arrays captured from the real per_gene_cpm_brainvar.py vs the API."""
import json, pathlib, math, urllib.request
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

SP = str(pathlib.Path(__file__).parent)
script = json.load(open(pathlib.Path(__file__).parent / "script_output.json"))

BOUNDS = [8*7,10*7,13*7,16*7,19*7,24*7,40*7,40*7+365/2,40*7+365,40*7+365*6,40*7+365*12]
LABELS = ['8w','10w','13w','16w','19w','24w','Birth','6m','1y','6y','12y']

fig, axes = plt.subplots(2, 2, figsize=(15, 10))
for ax, (sym, s) in zip(axes.ravel(), script.items()):
    api = json.loads(urllib.request.urlopen(f"http://localhost:8001/api/genes/{sym}/").read())
    gx = np.array(api["curve"]["log2_age_days"])

    ax.plot(s["x"], s["y"], 'o', ms=3, color='#bbbbbb', label='data points (identical, 1.8e-15)')
    ax.fill_between(s["band_x"], s["lower"], s["upper"], alpha=.22, color='crimson')
    ax.plot(s["curve_x"], s["curve_y"], color='crimson', lw=3,
            label='original script (skmisc default surface)')
    ax.fill_between(gx, api["curve"]["lower"], api["curve"]["upper"], alpha=.22, color='royalblue')
    ax.plot(gx, api["curve"]["fitted"], color='royalblue', lw=1.6, ls='--',
            label='web app (exact LOESS in numpy)')

    d = np.max(np.abs(np.interp(s["x"], gx, np.array(api["curve"]["fitted"])) - np.array(s["curve_y"])))
    ax.set_title(f"{sym} — curves differ by at most {d:.3f} log2", fontsize=11)
    ax.set_xticks([math.log(b,2) for b in BOUNDS]); ax.set_xticklabels(LABELS, fontsize=7)
    ax.set_ylabel("log2(CPM + 0.001)", fontsize=8)
    ax.legend(fontsize=7, loc='lower right'); ax.grid(alpha=.2)

fig.suptitle("Captured from the actual per_gene_cpm_brainvar.py (runpy) vs the web app's API",
             fontsize=13)
fig.tight_layout()
out = pathlib.Path(__file__).resolve().parent.parent / "data" / "output" / "verification_vs_original_script.png"
fig.savefig(out, dpi=110); print("saved", out)
