#!/usr/bin/python2
# -*- coding: utf-8 -*-

"""
Read mpstat.log file and convert it by aggregating values across NUMA nodes.

Read aggregation of CPUs from output of lscpu command.


Copyright 2017, Jarmila Hladká
Copyright 2020, Jirka Hladky, hladky DOT jiri AT gmail DOT com

License:
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from sys import stdin, stdout, stderr, exit

def get_input():
    """
    Parse and validate input line.
    """

    from argparse import ArgumentParser
    import os

    # Parse input line:
    usage = """

./mpstat2node.py --lscpu <(lscpu) < mpstat.log
or
mpstat -P ALL 5 | ./mpstat2node.py --lscpu <(lscpu)

Process mpstat output on the fly for the mpstat process which is already running:
1) mpstat -P ALL 5 > mpstat.txt
2) tail -f -n +1 mpstat.txt | mpstat2node.py --lscpu <(lscpu)

Retrieve mpstat output from another machine:
1) Collect mpstat data
lscpu > lscpu.txt
mpstat -P ALL 5 > mpstat.txt
2) Aggreagate mpstat data
./mpstat2node.py --lscpu lscpu.txt < mpstat.txt
"""

    description = """Converts output of mpstat -P ALL <time_interval>
        by aggregating values for NUMA node."""

    parser = ArgumentParser(description=description, usage=usage)
    parser.add_argument("--lscpu", help="Path to lscpu file.", required=True)
    args = parser.parse_args()

    # Return lscpu file:
    if args.lscpu:
        # Check if the file/link/pipe is readable:
        if os.access(args.lscpu, os.R_OK):
            return args.lscpu
        else:
            stderr.write("File {0} doesn't exist!\n".format(args.lscpu))
            exit(1)

    # If lscpu file isn't specified:
    else:
        stderr.write("Specify path to lscpu file using '--lscpu' option!\n")
        exit(1)


def CPU_NUMA(lscpu):
    """
    Make a dictionary of CPU's association with NUMA nodes.
    """

    with open(lscpu) as lscpufile:

        cpu_numa = {}
        numa_nodes_set = set()

        for line in lscpufile:

            # Find number of CPUs and NUMA nodes:
            if line[:7] == 'CPU(s):':
                cpu_nb = int(line[7:])
            elif line[:13] == 'NUMA node(s):':
                nodes_nb = int(line[13:])

            # Find NUMA nodes associated with CPUs:
            elif line[:9] == 'NUMA node':
                words = line.split()
                cpus = words[-1].split(',')
                numa_node = int(words[1][4:])
                numa_nodes_set.add(numa_node)
                for cpu in cpus:
                    if '-' in cpu:
                        w = cpu.split('-')
                        for i in range(int(w[0]), int(w[1]) + 1):
                            cpu_numa[str(i)] = numa_node
                    else:
                        cpu_numa[cpu] = numa_node

        # Check if all CPUs are associated with NUMA node:
        if len(cpu_numa) != cpu_nb:
            stderr.write("Error in CPU - node association!\n")
            exit(1)
        
        # Create list of NUMA nodes sorted by value
        numa_nodes = sorted(numa_nodes_set)

        # Check if nodes_nb == len(numa_nodes)
        if nodes_nb != len(numa_nodes):
            stderr.write("Warning - nodes_nb " + str(nodes_nb) + " is different from len(numa_nodes) " + str(len(numa_nodes)) + " !\n")
            stderr.write("          numa_nodes: " + " ".join(numa_nodes) + "\n")

        # Number of cpus on nodes:
        cpu_on_node = {}
        for node in numa_nodes:
            cpu_on_node[node] = cpu_numa.values().count(node)

    return cpu_numa, cpu_on_node, cpu_nb, numa_nodes


def modify_mpstat_output(cpu_numa, cpu_on_node, cpu_nb, nodes_nb):
    """
    Read mpstat output from stdin and output average activities
    among nodes.
    Ignore any lines at the top of the file starting with #
    """

    line = stdin.readline()
    if not line:
        stderr.write("WARN: Unexpected end of input file!\n")
        exit(1)
    line_count = 1

    while line.startswith("#"):
        stderr.write(line)
        line = stdin.readline()
        line_count += 1

    # Print the first line with the system info
    stdout.write(line)
    # Next line should be empty
    line = stdin.readline()
    if not line:
        stderr.write("WARN: Unexpected end of input file!\n")
        exit(1)
    line_count += 1
    stdout.write(line)
    if line != '\n':
        stderr.write("WARN: Expecting line number " + str(line_count) + " to be empty, but it's not.\n")

    # Loop over time reports.
    # Subsequent reports are separated by blank line:
    while True:

        status = average_over_node(cpu_numa, cpu_on_node, cpu_nb, numa_nodes, line_count)
        if status in ("END", "EOF"):
            break

    # Read and print final time statistics for nodes:
    if status == "END":
        average_over_node(cpu_numa, cpu_on_node, cpu_nb, numa_nodes, line_count)


def average_over_node(cpu_numa, cpu_on_node, cpu_nb, numa_nodes, line_count):
    """
    Read and print average statistics for one time interval report:
    """

    # Print description of columns:
    columns = stdin.readline()
    line_count += 1

    # Check for final time averages at the end of file:
    if columns == '\n':
        stdout.write('\n')
        return 'END'

    # Number of displayed CPU statistic values:
    STAT_COLUMNS = columns.count('%')

    # Write revised column labels:
    stdout.write('{0}{1}{2}'.format(columns[:12], 'NODE', columns[16:]))
    stdout.write(stdin.readline())
    line_count += 1

    # statistics - dictionary; key is the NUMA node number, value is the list of columns
    statistics = {}
    for key in numa_nodes:
        statistics[key] = [0.0] * STAT_COLUMNS
    #statistics = [[0.0 for j in range(len(numa_nodes))] for i in range(STAT_COLUMNS)]

    # Read statistics for CPUs:
    for i in range(cpu_nb):
        line = stdin.readline()
        line_count += 1
        words = line[11:].split()
        cpu = words[0]
        for col in range(STAT_COLUMNS):
            #print repr(words[col + 1])
            #try:
            statistics[cpu_numa[cpu]][col] += float(words[col + 1].strip('\0'))
            #except Exception as e:
            #    print str(e)
            #    print "col, cpu, node", col,cpu,cpu_numa[cpu]
                #print line
                


    # Statistics over nodes:
    for node in numa_nodes:
        output = '{0}{1:5d}'.format(line[:11], node)
        for col in range(STAT_COLUMNS):
            #print "node, col", node, col
            #print statistics[node][col]
            #print cpu_on_node[node]
            average = statistics[node][col]/cpu_on_node[node]
            output += '{0:8.2f}'.format(average)
        output += '\n'
        stdout.write(output)

    # Check for end of file without average values:
    next_line = stdin.readline()
    if next_line != '\n':
        return 'EOF'

    # If not end of file print blank line:
    stdout.write(next_line)
    line_count += 1


if __name__ == "__main__":

    cpu_numa, cpu_on_node, cpu_nb, numa_nodes = CPU_NUMA(get_input())
    modify_mpstat_output(cpu_numa, cpu_on_node, cpu_nb, numa_nodes)
