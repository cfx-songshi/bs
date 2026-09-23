"""Throwaway: what shape is the contact field output in an Explicit odb?"""
import sys

from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[0]]
frame = step.frames[-1]
print('frame at t=%.6g' % frame.frameValue)
for name, field in frame.fieldOutputs.items():
    values = getattr(field, 'values', None)
    print('%-10s type=%-24s locations=%s values=%s'
          % (name, field.type, field.locations, len(values) if values is not None else '-'))
    if values:
        sample = values[0]
        print('           sample: label=%s elementLabel=%s face=%s data=%s'
              % (getattr(sample, 'label', None), getattr(sample, 'elementLabel', None),
                 getattr(sample, 'face', None), sample.data))
        print('           instance=%s' % (sample.instance.name
                                          if getattr(sample, 'instance', None) else None))
        if len(values) > 1:
            print('           second: label=%s elementLabel=%s face=%s'
                  % (getattr(values[1], 'label', None),
                     getattr(values[1], 'elementLabel', None),
                     getattr(values[1], 'face', None)))
print('surfaces in odb:', list(getattr(odb.rootAssembly, 'surfaces', {}).keys()))
field = frame.fieldOutputs['CSDMG General_Contact_Domain']
location = field.locations[0]
print('location attributes:', [a for a in dir(location) if not a.startswith('_')])
for attribute in ('nodeLabels', 'elementLabels', 'faces', 'internalNodeLabels'):
    if hasattr(location, attribute):
        values = getattr(location, attribute)
        print('  %s: %s ... %s' % (attribute, values[:5], values[-3:]))
for attribute in ('nodeLabel', 'elementLabel', 'face', 'sectionPoint'):
    print('  value.%s: %s' % (attribute, getattr(field.values[5], attribute, 'no attr')))
odb.close()
