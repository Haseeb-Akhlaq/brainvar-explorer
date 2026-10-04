"""Compare the REAL script's plotted arrays against the web API's response."""
import json, pathlib, math, urllib.request
import numpy as np

script = json.load(open(pathlib.Path(__file__).parent / "script_output.json"))

print(f"{'gene':9} {'scatter x':>11} {'scatter y':>11} {'curve (interp)':>15} {'band lower':>11} {'band upper':>11}")
print("-" * 74)

for sym, s in script.items():
    api = json.loads(urllib.request.urlopen(f"http://localhost:8001/api/genes/{sym}/").read())

    # The script plots x = log2(AgeDays), y = log2(CPM + 1e-3), sorted by x.
    api_x = np.array(sorted(math.log2(p["age_days"]) for p in api["points"]))
    pts = sorted(api["points"], key=lambda p: math.log2(p["age_days"]))
    api_y = np.array([math.log2(p["cpm"] + 1e-3) for p in pts])

    dx = np.max(np.abs(api_x - np.array(s["x"])))
    dy = np.max(np.abs(api_y - np.array(s["y"])))

    # API curve is a 200-point grid; interpolate onto the script's 176 x values.
    gx = np.array(api["curve"]["log2_age_days"])
    fit = np.interp(s["x"], gx, np.array(api["curve"]["fitted"]))
    lo  = np.interp(s["x"], gx, np.array(api["curve"]["lower"]))
    hi  = np.interp(s["x"], gx, np.array(api["curve"]["upper"]))

    dc = np.max(np.abs(fit - np.array(s["curve_y"])))
    dl = np.max(np.abs(lo - np.array(s["lower"])))
    du = np.max(np.abs(hi - np.array(s["upper"])))

    print(f"{sym:9} {dx:11.3e} {dy:11.3e} {dc:15.4f} {dl:11.4f} {du:11.4f}")
