#!/usr/bin/env python3
"""
Ultra-simple HTTP server for backend - no frameworks, just raw HTTP
"""
import socket
import json
from threading import Thread

def handle_request(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()
        lines = request.split('\r\n')
        method_line = lines[0].split()
        
        if len(method_line) < 2:
            return
        
        method = method_line[0]
        path = method_line[1]
        
        # Route: /health
        if path == '/health' and method == 'GET':
            response = json.dumps({"status": "ok", "message": "Backend is running"})
            http_response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{response}"
            client_socket.sendall(http_response.encode())
        
        # Route: /
        elif path == '/' and method == 'GET':
            response = json.dumps({"message": "AI Hospitality Navigator Backend", "version": "1.0"})
            http_response = f"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\nAccess-Control-Allow-Origin: *\r\n\r\n{response}"
            client_socket.sendall(http_response.encode())
        
        # OPTIONS for CORS
        elif method == 'OPTIONS':
            http_response = "HTTP/1.1 200 OK\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: *\r\n\r\n"
            client_socket.sendall(http_response.encode())
        
        else:
            response = json.dumps({"error": "Not Found"})
            http_response = f"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {len(response)}\r\n\r\n{response}"
            client_socket.sendall(http_response.encode())
    
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client_socket.close()

def start_server(host='127.0.0.1', port=8000):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Server running on http://{host}:{port}")
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            client_socket, addr = server_socket.accept()
            thread = Thread(target=handle_request, args=(client_socket, addr), daemon=True)
            thread.start()
    except KeyboardInterrupt:
        print("\nServer stopped")
    finally:
        server_socket.close()

if __name__ == '__main__':
    start_server()
