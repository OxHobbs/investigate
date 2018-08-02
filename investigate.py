import sys
import os
import re

# with open('/tmp/test', 'w') as f:
#     f.writelines(sys.version)

sdc_devices = sorted([d for d in os.listdir('/dev') if re.match(r'sdc\d+', d)])

for sdc in sdc_devices:
    os.mkdir(os.path.join('/mnt', sdc))
