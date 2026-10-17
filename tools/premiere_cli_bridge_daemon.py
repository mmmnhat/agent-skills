import http.server
import json
import os
import time
import uuid

PORT = 47823
PANEL_VERSION = "0.4.3"
PLUGIN_DIR = "C:/Users/AMZ-HUY/AppData/Roaming/Adobe/CEP/extensions/com.stefanwebb.premierecli"
BRIDGE_DIR = r"C:\Users\AMZ-HUY\premiere-mcp-bridge"
INDEX_JSX = PLUGIN_DIR + "/host/index.jsx"


def eval_in_premiere(command: str, args: dict) -> dict:
    args_with_ctx = dict(args or {})
    args_with_ctx["pluginDir"] = PLUGIN_DIR
    args_json = json.dumps(args_with_ctx, ensure_ascii=False)
    cid = "ppb_" + uuid.uuid4().hex[:8]
    cmd_path = os.path.join(BRIDGE_DIR, f"cmd_{cid}.jsx")
    res_path = os.path.join(BRIDGE_DIR, f"res_{cid}.json")

    jsx = f"""(function() {{
  try {{
    if (typeof JSON === "undefined") {{ JSON = {{}}; }}
    if (typeof JSON.parse !== "function") {{
      JSON.parse = function(s) {{ return eval("(" + String(s) + ")"); }};
    }}
    if (typeof JSON.stringify !== "function") {{
      $.evalFile({json.dumps(INDEX_JSX)});
    }}
    if (typeof ppb_dispatch !== "function" || typeof __PPB_V3 === "undefined") {{
      $.evalFile({json.dumps(INDEX_JSX)});
      __PPB_V3 = true;
    }}
    return ppb_dispatch({json.dumps(command)}, {json.dumps(args_json)});
  }} catch (e) {{
    return JSON.stringify({{ ok: false, error: e.toString() }});
  }}
}})();"""

    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write(jsx)

    for _ in range(2400):
        if os.path.exists(res_path):
            time.sleep(0.03)
            try:
                raw = open(res_path, "r", encoding="utf-8").read()
            finally:
                try:
                    os.remove(res_path)
                except Exception:
                    pass
                try:
                    os.remove(cmd_path)
                except Exception:
                    pass
            try:
                return json.loads(raw)
            except Exception:
                return {"ok": False, "error": f"unparsable result: {raw}"}
        time.sleep(0.05)

    try:
        os.remove(cmd_path)
    except Exception:
        pass
    return {"ok": False, "error": "timeout waiting for Premiere ExtendScript bridge"}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/ping":
            self._send_json(200, {"ok": True, "panelVersion": PANEL_VERSION})
        else:
            self._send_json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
        try:
            parsed = json.loads(raw_body)
        except Exception:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return

        if self.path == "/log":
            self._send_json(200, {"ok": True})
            return

        if self.path == "/command":
            cmd = parsed.get("command")
            if not cmd or not isinstance(cmd, str):
                self._send_json(400, {"ok": False, "error": "command is required"})
                return
            res = eval_in_premiere(cmd, parsed.get("args") or {})
            self._send_json(200, res)
            return

        self._send_json(404, {"ok": False, "error": "not found"})


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Premiere CLI Bridge Daemon listening on http://127.0.0.1:{PORT}", flush=True)
    server.serve_forever()
