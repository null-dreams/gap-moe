#!/usr/bin/env python3
import subprocess
import sys
import time

LAB_NAME = "gap-moe" # Matches your verified lab name

def run_cmd(cmd):
    return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def start_traffic():
    print("[*] Starting iperf3 Server inside the 'hub' network namespace...")
    # Run server in the background sharing clab-gap-moe-hub namespace
    server_cmd = (
        f"docker run -d --name clab-iperf-server "
        f"--net=container:clab-{LAB_NAME}-hub "
        f"networkstatic/iperf3 -s"
    )
    run_cmd("docker rm -f clab-iperf-server") # Clean up if running
    res = run_cmd(server_cmd)
    if res.returncode != 0:
        print(f"[-] Failed to start server: {res.stderr}")
        sys.exit(1)

    time.sleep(2) # Let the server bind

    print("[*] Starting iperf3 Client inside the 'branch-1' network namespace...")
    # Send continuous traffic from branch-1 to the hub's dynamic OSPF IP (10.0.0.1) for 1 hour
    client_cmd = (
        f"docker run -d --name clab-iperf-client "
        f"--net=container:clab-{LAB_NAME}-branch-1 "
        f"networkstatic/iperf3 -c 10.0.0.1 -t 3600 -b 2m"
    )
    run_cmd("docker rm -f clab-iperf-client") # Clean up if running
    res = run_cmd(client_cmd)
    if res.returncode != 0:
        print(f"[-] Failed to start client: {res.stderr}")
        sys.exit(1)
        
    print("[+] Traffic generation active! (2 Mbps stream from branch-1 -> hub)")

def stop_traffic():
    print("[*] Tearing down traffic generators...")
    run_cmd("docker rm -f clab-iperf-server clab-iperf-client")
    print("[+] Traffic generators stopped.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 traffic_generator.py [start|stop]")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    if action == "start":
        start_traffic()
    elif action == "stop":
        stop_traffic()
    else:
        print("[-] Invalid action. Use 'start' or 'stop'.")