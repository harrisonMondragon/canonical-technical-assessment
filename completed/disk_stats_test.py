# Python conversion of disk_stats_test.sh

#!/usr/bin/env python3

import sys
import os
import time
import subprocess

DISK = "sda"
STATUS = 0

def check_return_code(retval, message, *args):
    global STATUS
    if retval != 0:
        print(f"ERROR: retval {retval} : {message}", file=sys.stderr)
        if STATUS == 0:
            STATUS = retval
        if args:
            for item in args:
                print(f"output: {item}")

def main():
    global DISK, STATUS

    if len(sys.argv) > 1:
        DISK = sys.argv[1]

    nvdimm = "pmem"
    if nvdimm in DISK:
        print(f"Disk {DISK} appears to be an NVDIMM, skipping")
        sys.exit(STATUS)

    # Check /proc/partitions
    try:
        with open("/proc/partitions", "r") as f:
            partitions = f.read()
        if DISK not in partitions:
            check_return_code(1, f"Disk {DISK} not found in /proc/partitions")
    except FileNotFoundError:
        check_return_code(1, f"/proc/partitions not found")

    # Check /proc/diskstats
    try:
        with open("/proc/diskstats", "r") as f:
            diskstats = f.read()
        if DISK not in diskstats:
            check_return_code(1, f"Disk {DISK} not found in /proc/diskstats")
    except FileNotFoundError:
        check_return_code(1, f"/proc/diskstats not found")

    # Verify the disk shows up in /sys/block/
    if not os.path.exists(f"/sys/block/{DISK}"):
        check_return_code(1, f"Disk {DISK} not found in /sys/block")

    # Verify there are stats in /sys/block/$DISK/stat
    if not os.path.isfile(f"/sys/block/{DISK}/stat") or os.stat(f"/sys/block/{DISK}/stat").st_size == 0:
        check_return_code(1, f"stat is either empty or non-existent in /sys/block/{DISK}/stat")

    # Get some baseline stats for use later
    try:
        with open("/proc/diskstats", "r") as f:
            matched_lines = [line for line in f if DISK in line]
            if not matched_lines:
                check_return_code(1, f"No stats found for disk {DISK} in /proc/diskstats")
            PROC_STAT_BEGIN = matched_lines[0]  # Get the first matching line
            
        with open(f"/sys/block/{DISK}/stat", "r") as f:
            SYS_STAT_BEGIN = f.read()
            if not SYS_STAT_BEGIN.strip():  # Check if the read data is empty
                check_return_code(1, f"Stat file is empty in /sys/block/{DISK}/stat")
    except FileNotFoundError:
        check_return_code(1, f"Failed to retrieve stats for {DISK}")

    # Generate some disk activity using hdparm -t
    try:
        subprocess.run(["hdparm", "-t", f"/dev/{DISK}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        check_return_code(1, f"Error running hdparm: {str(e)}")

    # Sleep 5 to let the stats files catch up
    time.sleep(5)

    # Make sure the stats have changed
    try:
        with open("/proc/diskstats", "r") as f:
            PROC_STAT_END = [line for line in f if DISK in line][0]
        with open(f"/sys/block/{DISK}/stat", "r") as f:
            SYS_STAT_END = f.read()
        
        if PROC_STAT_BEGIN == PROC_STAT_END:
            check_return_code(1, "Stats in /proc/diskstats did not change", PROC_STAT_BEGIN, PROC_STAT_END)

        if SYS_STAT_BEGIN == SYS_STAT_END:
            check_return_code(1, f"Stats in /sys/block/{DISK}/stat did not change", SYS_STAT_BEGIN, SYS_STAT_END)

    except FileNotFoundError:
        check_return_code(1, f"Failed to read updated stats for {DISK}")

    if STATUS == 0:
        print(f"PASS: Finished testing stats for {DISK}")

    sys.exit(STATUS)

if __name__ == "__main__":
    main()
