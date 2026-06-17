#!/usr/bin/env python3
import subprocess
import sys

LAB_NAME = "gap-moe"

def run_docker_exec(container, cmd):
    full_cmd = f"docker exec {container} {cmd}"
    res = subprocess.run(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res

def run_docker_exec_detached(container, cmd):
    full_cmd = f"docker exec -d {container} {cmd}"
    res = subprocess.run(full_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res

def handle_clear():
    print("[*] Resetting all network namespaces to normal...")
    # Clear tc qdiscs (suppress errors if no qdisc exists)
    run_docker_exec(f"clab-{LAB_NAME}-transit", "tc qdisc del dev eth1 root")
    run_docker_exec(f"clab-{LAB_NAME}-transit", "tc qdisc del dev eth2 root")
    run_docker_exec(f"clab-{LAB_NAME}-transit", "tc qdisc del dev eth3 root")
    run_docker_exec(f"clab-{LAB_NAME}-hub", "tc qdisc del dev eth1 root")
    # Kill memory leak processes
    run_docker_exec(f"clab-{LAB_NAME}-transit", "pkill -f 'dev/urandom'")
    run_docker_exec(f"clab-{LAB_NAME}-transit", "pkill -f urandom")
    print("[+] All chaos cleared. Network operating normally.")

def inject_congestion(stage):
    # Target: transit to hub (eth1) interface bottleneck
    dev = "eth1"
    container = f"clab-{LAB_NAME}-transit"
    
    # Clear existing rules first
    run_docker_exec(container, f"tc qdisc del dev {dev} root")
    
    if stage == "warn":
        print("[*] Injecting Congestion [STAGE: WARNING] - Limiting transit-hub link to 500Kbps...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root tbf rate 500kbit latency 50ms burst 1540")
    elif stage == "crit":
        print("[*] Injecting Congestion [STAGE: CRITICAL] - Limiting transit-hub link to 80Kbps...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root tbf rate 80kbit latency 50ms burst 1540")

def inject_flapping(stage):
    # Target: branch-1 to transit link (transit dev eth2)
    dev = "eth2"
    container = f"clab-{LAB_NAME}-transit"
    
    run_docker_exec(container, f"tc qdisc del dev {dev} root")
    
    if stage == "warn":
        print("[*] Injecting Flapping Precursor [STAGE: WARNING] - 10% packet drop on transit-branch1...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root netem loss 10%")
    elif stage == "crit":
        print("[*] Injecting Flapping Precursor [STAGE: CRITICAL] - 35% packet drop (OSPF Hello messages will fail)...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root netem loss 35%")

def inject_degradation(stage):
    # Target: transit-branch2 link (transit dev eth3)
    dev = "eth3"
    container = f"clab-{LAB_NAME}-transit"
    
    run_docker_exec(container, f"tc qdisc del dev {dev} root")
    
    if stage == "warn":
        print("[*] Injecting Latency Degradation [STAGE: WARNING] - Adding 120ms delay on transit-branch2...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root netem delay 120ms")
    elif stage == "crit":
        print("[*] Injecting Latency Degradation [STAGE: CRITICAL] - Adding 450ms delay on transit-branch2...")
        run_docker_exec(container, f"tc qdisc add dev {dev} root netem delay 450ms")

def inject_leak(stage):
    # Target: transit node memory space
    # Clean up previous leaks
    container = f"clab-{LAB_NAME}-transit"
    run_docker_exec(container, "pkill -f urandom")
    
    if stage == "warn":
        print("[*] Injecting Routing Engine Memory Leak [STAGE: WARNING] - Appending ~2MB/sec to memory...")
        # Appends random data to a POSIX shell variable in background inside the container
        run_docker_exec_detached(container, "sh -c \"v=''; while true; do v=\\$v\\$(head -c 2097152 < /dev/urandom); sleep 1; done\"")
    elif stage == "crit":
        print("[*] Injecting Routing Engine Memory Leak [STAGE: CRITICAL] - Appending ~8MB/sec to memory...")
        run_docker_exec_detached(container, "sh -c \"v=''; while true; do v=\\$v\\$(head -c 8388608 < /dev/urandom); sleep 1; done\"")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 chaos_injector.py [congestion|flapping|degradation|leak|clear] [warn|crit]")
        sys.exit(1)
        
    scenario = sys.argv[1].lower()
    
    if scenario == "clear":
        handle_clear()
        sys.exit(0)
        
    if len(sys.argv) < 3:
        print("[-] You must specify a stage: 'warn' or 'crit'")
        sys.exit(1)
        
    stage = sys.argv[2].lower()
    if stage not in ["warn", "crit"]:
        print("[-] Invalid stage. Choose 'warn' or 'crit'.")
        sys.exit(1)
        
    if scenario == "congestion":
        inject_congestion(stage)
    elif scenario == "flapping":
        inject_flapping(stage)
    elif scenario == "degradation":
        inject_degradation(stage)
    elif scenario == "leak":
        inject_leak(stage)
    else:
        print("[-] Unknown scenario name.")