#!/usr/bin/python3

import json
import signal
from http.server import SimpleHTTPRequestHandler, HTTPServer
import subprocess

# Align those commands to your usecase
ON_COMMAND = "gpio mode 7 output; gpio write 7 1"
OFF_COMMAND = "gpio write 7 0"
STATUS_COMMAND = "gpio read 7"

running = True

def exit_gracefully(*args, **kwargs):
    print("Terminating...")
    global running
    running = False

signal.signal(signal.SIGINT, exit_gracefully)
signal.signal(signal.SIGTERM, exit_gracefully)


class MyHttpRequestHandler(SimpleHTTPRequestHandler):

      def do_GET(self):
         self.send_response(200)
         self.send_header('Content-type', 'application/json')
         self.end_headers()

         if self.path == "/on":
             # using shell=True allows us to send multiple commands separated by ;
             subprocess.run(ON_COMMAND, shell=True)
         elif self.path == "/off":
             subprocess.run(OFF_COMMAND, shell=True)
         ret = subprocess.run(STATUS_COMMAND, capture_output=True, shell=True)
         # rework this part to align it to output of your command
         # it should return 'on' or 'off' for key 'status' in return dictionary 
         status = ret.stdout.decode().strip()
         status = 'on' if status == '1' else 'off'
         # send reponse with switch status
         self.wfile.write(json.dumps({'status': status}).encode("utf-8"))


if __name__ == '__main__':
    server_class = HTTPServer
    handler_class = MyHttpRequestHandler
    server_address = ('127.0.0.1', 56427)

    httpd = server_class(server_address, handler_class)
    # intentionally making it slow, it doesn't need to react quickly
    httpd.timeout = 1  # seconds

    try:
        while running:
            httpd.handle_request()
    except KeyboardInterrupt:
        pass
