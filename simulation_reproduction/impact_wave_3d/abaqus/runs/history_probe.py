"""Throwaway: what history regions and outputs did the odb actually get?"""
import sys

from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[0]]
print('step %s, %d regions' % (step.name, len(step.historyRegions)))
for name in list(step.historyRegions.keys())[:12]:
    region = step.historyRegions[name]
    print('  %-28s %s' % (name, ', '.join(sorted(region.historyOutputs.keys()))))
elements = [name for name in step.historyRegions.keys() if name.lower().startswith('element')]
print('regions whose name starts with "Element": %d' % len(elements))
for name in elements[:6]:
    print('  %s -> %s' % (name, ', '.join(sorted(step.historyRegions[name]
                                                 .historyOutputs.keys()))))
odb.close()
