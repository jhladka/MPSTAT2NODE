#!/usr/bin/python2
# -*- coding: utf-8 -*-

"""
Read mpstat.log file and convert it by aggregating values across NUMA nodes.

Read aggregation of CPUs from output of lscpu command.


Copyright 2017, Jarmila Hladká

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
            stderr.write("File {} doesn't exist!\n".format(args.lscpu))
            exit(1)

    # If lscpu file isn't specified:
    else:
        stderr.write("Specify path to lscpu file using '--lscpu' option!\n")
        exit(1)


def CPU_NUMA(lscpu):
    """
    Make a dictionnary of CPU's association with NUMA nodes.
    """

    with open(lscpu) as lscpufile:

        cpu_numa = {}

        for line in lscpufile:

            # Find number of CPUs and NUMA nodes:
            if line[:7] == 'CPU(s):':
                cpu_nb = int(line[7:])
            if line[:13] == 'NUMA node(s):':
                nodes_nb = int(line[13:])

            # Find NUMA nodes associated with CPUs:
            if line[:9] == 'NUMA node':
                words = line.split()
                cpus = words[-1].split(',')
                for cpu in cpus:
                    if '-' in cpu:
                        w = cpu.split('-')
                        for i in range(int(w[0]), int(w[1]) + 1):
                            cpu_numa[str(i)] = words[1][-1:]
                    else:
                        cpu_numa[cpu] = words[1][-1:]

        # Check if all CPUs are associated with NUMA node:
        if len(cpu_numa) != cpu_nb:
            stderr.write("Error in CPU - node association!\n")
            exit(1)

        # Number of cpus on nodes:
        cpu_on_node = [cpu_numa.values().count(str(node)) for node in range(nodes_nb)]

    return cpu_numa, cpu_on_node, cpu_nb, nodes_nb


def modify_mpstat_output(cpu_numa, cpu_on_node, cpu_nb, nodes_nb):
    """
    Read mpstas output from stdin and output average activities
    among nodes.
    """

    # Print first two lines with system info:
    for i in range(2):
        stdout.write(stdin.readline())

    # Loop over time reports.
    # Subsequent reports are separated by blank line:
    while True:

        status = average_over_node(cpu_numa, cpu_on_node, cpu_nb, nodes_nb)
        if status in ("END", "EOF"):
            break

    # Read and print final time statistics for nodes:
    if status == "END":
        average_over_node(cpu_numa, cpu_on_node, cpu_nb, nodes_nb)


def average_over_node(cpu_numa, cpu_on_node, cpu_nb, nodes_nb):
    """
    Read and print average statistics for one time interval report:
    """

    # Print description of columns:
    columns = stdin.readline()

    # Check for final time averages at the end of file:
    if columns == '\n':
        stdout.write('\n')
        return 'END'

    # Number of displayed CPU statistic values:
    STAT_COLUMNS = columns.count('%')

    # Write revised column labels:
    stdout.write('{0}{1}{2}'.format(columns[:12], 'NODE', columns[16:]))
    stdout.write(stdin.readline())

    # List for statistics:
    statistics = [[0.0 for j in range(nodes_nb)] for i in range(STAT_COLUMNS)]

    # Read statistics for CPUs:
    for i in range(cpu_nb):
        line = stdin.readline()
        words = line[11:].split()
        cpu = words[0]
        for col in range(STAT_COLUMNS):
            statistics[col][int(cpu_numa[cpu])] += float(words[col + 1])

    # Statistics over nodes:
    for node in range(nodes_nb):
        output = '{0}{1:5d}'.format(line[:11], node)
        for col in range(STAT_COLUMNS):
            average = statistics[col][node]/cpu_on_node[node]
            output += '{0:8.2f}'.format(average)
        output += '\n'
        stdout.write(output)

    # Check for end of file without average values:
    next_line = stdin.readline()
    if next_line != '\n':
        return 'EOF'

    # If not end of file print blank line:
    stdout.write(next_line)


if __name__ == "__main__":

    cpu_numa, cpu_on_node, cpu_nb, nodes_nb = CPU_NUMA(get_input())
    modify_mpstat_output(cpu_numa, cpu_on_node, cpu_nb, nodes_nb)
