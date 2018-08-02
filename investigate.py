import sys
import os
import re
import subprocess
# with open('/tmp/test', 'w') as f:
#     f.writelines(sys.version)

sdc_devices = sorted([d for d in os.listdir('/dev') if re.match(r'sdc\d+', d)])

for sdc in sdc_devices:
    mnt_path = os.path.join('/mnt', sdc)
    os.mkdir(mnt_path)

    if not os.path.ismount(sdc):
        subprocess.call(['mount', os.path.join('/dev', sdc), mnt_path])

