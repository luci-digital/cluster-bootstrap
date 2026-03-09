#!/usr/bin/env python3
"""
AIFAM TB Cluster Registration Server
Runs on Zbook (head node) to track worker registrations
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import datetime
import os

CLUSTER_STATE_FILE = "/var/lib/tb-cluster/nodes.json"

class TBClusterHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/tb-cluster/register":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            try:
                data = json.loads(body)
                node = data.get('node', 'unknown')
                ip = data.get('ip', 'unknown')
                mac = data.get('mac', 'unknown')
                
                # Load existing state
                nodes = {}
                if os.path.exists(CLUSTER_STATE_FILE):
                    with open(CLUSTER_STATE_FILE, 'r') as f:
                        nodes = json.load(f)
                
                # Update node
                nodes[node] = {
                    'ip': ip,
                    'mac': mac,
                    'last_seen': datetime.datetime.now().isoformat(),
                    'status': 'online'
                }
                
                # Save state
                os.makedirs(os.path.dirname(CLUSTER_STATE_FILE), exist_ok=True)
                with open(CLUSTER_STATE_FILE, 'w') as f:
                    json.dump(nodes, f, indent=2)
                
                print(f"[TB-CLUSTER] Node registered: {node} @ {ip} ({mac})")
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'ok'}).encode())
                
            except Exception as e:
                print(f"[TB-CLUSTER] Error: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_GET(self):
        if self.path == "/tb-cluster/nodes":
            nodes = {}
            if os.path.exists(CLUSTER_STATE_FILE):
                with open(CLUSTER_STATE_FILE, 'r') as f:
                    nodes = json.load(f)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(nodes, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8742), TBClusterHandler)
    print("[TB-CLUSTER] Registration server running on port 8742")
    server.serve_forever()
