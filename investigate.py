import sys

with open('/tmp/test', 'w') as f:
    f.writelines(sys.version)
