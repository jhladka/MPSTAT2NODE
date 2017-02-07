# MPSTAT2NODE

Read mpstat.log file and convert it by aggregating values across NUMA nodes.
Read aggregation of CPUs from output of lscpu command.

**Usage**

./mpstat2node.py --lscpu <(lscpu) < mpstat.log

or

mpstat -P ALL 5 | ./mpstat2node.py --lscpu <(lscpu)

**Process mpstat output on the fly for the mpstat process which is already running:**

1) nmpstat -P ALL 5 > mpstat.txt

2) tail -f -n +1 mpstat.txt | mpstat2node.py --lscpu <(lscpu)

**Retrieve mpstat output from another machine:**

1) Collect mpstat data

lscpu > lscpu.txt

mpstat -P ALL 5 > mpstat.txt

2) Aggreagate mpstat data

./mpstat2node.py --lscpu lscpu.txt < mpstat.txt
