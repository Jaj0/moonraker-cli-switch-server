# moonraker-cli-switch-server
How to control power switch using cli command



![image](https://github.com/user-attachments/assets/5460d8dd-af88-4082-9ab7-d90816550691)
![PrinterTurnOn](https://github.com/user-attachments/assets/8f0fbed1-637a-4e19-8a59-028b1c947fa2)

👎 There's no way to run cli command to switch on/off custom power supply device through moonraker (yet, but i've raised feature request: https://github.com/Arksine/moonraker/issues/932).

👎 Klipper can run macros, but these only run if the MCU is connected, which requires the power to be on in the first place. 

🍀 Luckily the `power` section of Moonraker's config allows arbitrary http requests (even if `type: http` is, confusingly, not explicitly called out as supported in the documentation), a Python script with a tiny HTTP server attached can be used to send correct shell commands:

![image](https://github.com/user-attachments/assets/ff50eb1b-3b45-495c-bbfc-686ae7c7abf2)

# Here's how:
1. Save this script somewhere, for example `/home/pi/switch/server.py`, then edit the `ON_COMMAND`, `OFF_COMMAND`, `STATUS_COMMAND` fields appropriately. Also rework parsing of `STATUS_COMMAND` return value to match 'on'/'off' status value.

⚠ **Note:** this is the code for the custiom gpio library for NanoPi Neo Air ([WiringNP](https://github.com/friendlyarm/WiringNP)).
  ```python3
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
  ```
2. Make the script executable `chmod +x /home/pi/switch/server.py`.
3. Make the script autostart, create a service with your editor of choice, e.g. `sudo nano /etc/systemd/system/switch.service`
  ```
  [Unit]
  Description=CLI Switch server
  Wants=network.target
  After=network.target
  
  [Service]
  User=pi
  Group=pi
  ExecStartPre=/bin/sleep 10
  ExecStart=/home/pi/switch/server.py
  Restart=always
  
  [Install]
  WantedBy=multi-user.target
 ```
4. Start your service `service switch start`, if something goes wrong you can check status `service switch status` and logs `journalctl -u switch`. Then enable it so it autostarts `systemctl enable switch.service`
5. Open in Mainsail/Fluidd your `Moonraker.cfg`, add this at the end (and maybe customise the device name just after "power"):
```
[power printer]
type: http
on_url: http://localhost:56427/on
off_url: http://localhost:56427/off
status_url: http://localhost:56427/
response_template:
  {% set resp = http_request.last_response().json() %}
  {resp["status"]}
bound_services: klipper
```
6. Restart Moonraker and that should be all.

Optional goodies for `Moonraker.cfg`, to add below `[power printer]`
```
off_when_shutdown: True
locked_while_printing: True
restart_klipper_when_powered: True
on_when_job_queued: True
```

Optional Klipper auto power off, courtesy of https://github.com/Arksine/moonraker/issues/167#issuecomment-1094223802

Add to `Printer.cfg` or any Klipper config, adjust device name if needed:
```
[idle_timeout]
timeout: 600
gcode:
  MACHINE_IDLE_TIMEOUT

# Turn on PSU
[gcode_macro M80]
gcode:
  # Moonraker action
  {action_call_remote_method('set_device_power',
                             device='printer',
                             state='on')}

# Turn off PSU
[gcode_macro M81]
gcode:
  # Moonraker action
  {action_call_remote_method('set_device_power',
                             device='printer',
                             state='off')}

[gcode_macro MACHINE_IDLE_TIMEOUT]
gcode:
  M84
  TURN_OFF_HEATERS
  M81
```
Thanks to user https://github.com/mainde for original idea on which i've based my solution!
