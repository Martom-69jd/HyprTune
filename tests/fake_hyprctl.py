#!/usr/bin/env python3
"""A stand-in for hyprctl that mimics Hyprland 0.56 (Lua) or 0.54 (hyprlang) responses.

Env: FAKE_STYLE=lua|hyprlang  FAKE_LOG=<file>  FAKE_MISSING=a,b  FAKE_LIVE=<json file of key->value>"""
import json, os, sys
args = sys.argv[1:]
style = os.environ.get("FAKE_STYLE", "lua")
log = os.environ.get("FAKE_LOG")
def note(*a):
    if log:
        with open(log, "a") as f: f.write(" ".join(a) + "\n")
jflag = "-j" in args
args = [a for a in args if a != "-j"]
if jflag:
    if args[0] == "getoption":
        key = args[1]
        schema = json.load(open(os.path.join(os.path.dirname(__file__), "..", "src", "hyprtune", "data", "hypr_options.json")))["options"]
        if key in os.environ.get("FAKE_MISSING", "").split(",") or key not in schema:
            print("no such option"); sys.exit(0)
        m = schema[key]; t = m["type"]
        live = json.load(open(os.environ["FAKE_LIVE"])) if os.environ.get("FAKE_LIVE") else {}
        d = live.get(key, m.get("default"))
        if t == "bool":   body = f'"bool": {"true" if d else "false"}'
        elif t == "int":  body = f'"int": {d}'
        elif t == "cssgap": body = f'"custom": "{d} {d} {d} {d}"'
        elif t == "float": body = f'"float": {float(d):.6f}'
        elif t == "choice": body = f'"int": {d if isinstance(d,int) else m["enum"].index(d)}'
        elif t == "string": body = f'"str": "{d}"'
        elif t == "color": body = f'"int": {int(d,16) if isinstance(d,str) else d}'
        elif t == "gradient":
            v = d if isinstance(d, str) else ""
            body = '"custom": "%s"' % (" ".join(f"{int(x,16):x}" for x in v.split()[:1]) + " 0deg" if v.startswith("0x") else "ee33ccff ee00ff99 45deg")
        else: body = f'"str": "{d}"'
        print(f'{{"option": "{key}", {body}, "set": false }}'); sys.exit(0)
    if args[0] == "version":
        print(json.dumps({"version": "0.56.0", "tag": "v0.56.0" if style == "lua" else "v0.54.2"})); sys.exit(0)
cmd = args[0] if args else ""
if cmd == "eval":
    note("eval", args[1])
    print("ok" if style == "lua" else "eval is only supported with the lua config manager")
elif cmd == "--batch":
    parts = [p.strip() for p in args[1].split(" ; ")]
    for p in parts: note(p)
    print("\n".join("ok" for _ in parts))
elif cmd == "reload": note("reload"); print("ok")
elif cmd == "configerrors": print(os.environ.get("FAKE_ERRORS", ""))
else: print("unknown request", file=sys.stderr); sys.exit(1)
