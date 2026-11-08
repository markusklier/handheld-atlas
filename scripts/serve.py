"""Local preview. Bind to loopback by default; never expose credentials or sources."""
import argparse
import http.server
from pathlib import Path
import functools

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description='Serve the built Handheld Atlas PWA')
parser.add_argument('--port',type=int,default=8765)
parser.add_argument('--host',default='127.0.0.1')
args = parser.parse_args()
if not (ROOT/'dist/index.html').exists():
    from build import build
    build()
class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,'.webmanifest':'application/manifest+json'}
    def end_headers(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-cache')
        self.send_header('Referrer-Policy','no-referrer')
        super().end_headers()
handler = functools.partial(Handler,directory=str(ROOT/'dist'))
print(f'Atlas: http://{args.host}:{args.port} (Ctrl+C to stop)',flush=True)
try:
    with http.server.ThreadingHTTPServer((args.host,args.port),handler) as server:
        server.serve_forever()
except KeyboardInterrupt:
    pass
