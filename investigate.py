import sys
import os
import re
import subprocess
import gzip
import shutil

# with open('/tmp/test', 'w') as f:
#     f.writelines(sys.version)

sdc_devices = sorted([d for d in os.listdir('/dev') if re.match(r'sdc\d+', d)])

for sdc in sdc_devices:
    mnt_path = os.path.join('/mnt', sdc)

    if not os.path.exists(mnt_path):
        os.mkdir(mnt_path)

    if not os.path.ismount(mnt_path):
        print("Mounting {} to {}".format(sdc, mnt_path))
        subprocess.call(['mount', os.path.join('/dev', sdc), mnt_path])
    else:
        print("{} is ALREADY mounted at {}".format(sdc, mnt_path))
    
    messages_path = os.path.join(mnt_path, 'var', 'log', 'messages')
    messages_arch_path = os.path.join('/tmp', 'messages_archive.txt.gz')
    
    if os.path.exists(messages_path):
        print('Found messages log in path: {}'.format(mnt_path))

        with open(messages_path, 'rb') as f_in, gzip.open(messages_arch_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
