"""
CartSaver -- Local Dashboard Server
Serves the dashboard folder and handles dynamic API refresh requests.
"""

import os
import sys
import subprocess
import json
import webbrowser
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8000
ROOT_DIR = Path(__file__).resolve().parent.parent

class DashboardHandler(SimpleHTTPRequestHandler):
    def do_POST(self):
        """Intercept POST requests to run the data generator dynamically."""
        if self.path == '/api/refresh':
            print("Received refresh request from dashboard dashboard UI...")
            try:
                script_path = ROOT_DIR / "dashboard" / "generate_data.py"
                
                # Execute generate_data.py as a subprocess to refresh database stats and contact Llama 3.1 NIM
                result = subprocess.run(
                    [sys.executable, str(script_path)],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=str(ROOT_DIR)
                )
                print("Successfully refreshed data.json via generate_data.py!")
                print(result.stdout)
                
                # Send HTTP success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                
                response_data = {
                    "status": "success",
                    "message": "Database query completed & Llama 3.1 briefing generated successfully."
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except subprocess.CalledProcessError as err:
                print(f"Error executing generate_data.py script: {err}")
                print(f"Script stdout: {err.stdout}")
                print(f"Script stderr: {err.stderr}")
                
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response_data = {
                    "status": "error",
                    "message": "Subprocess execution failed.",
                    "details": err.stderr
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except Exception as exc:
                print(f"Unexpected error handling dashboard refresh: {exc}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                
                response_data = {
                    "status": "error",
                    "message": str(exc)
                }
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def main():
    # Ensure current directory context is set to project root
    os.chdir(str(ROOT_DIR))
    
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, DashboardHandler)
    
    dashboard_url = f"http://localhost:{PORT}/dashboard/index.html"
    print(f"\n==========================================================================")
    print(f"  CartSaver Dashboard Server is active!")
    print(f"  URL: {dashboard_url}")
    print(f"  Root Serving Path: {ROOT_DIR}")
    print(f"  Press Ctrl+C in this terminal window to stop the server.")
    print(f"==========================================================================\n")
    
    # Automatically open the dashboard in the system's default web browser
    webbrowser.open(dashboard_url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping CartSaver dashboard server...")
        httpd.server_close()
        print("Server stopped. Goodbye!")

if __name__ == "__main__":
    main()
