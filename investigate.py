import sys
import os
import re
import subprocess
import gzip
import shutil
from azure_storage import BlockBlobService

# with open('/tmp/test', 'w') as f:
#     f.writelines(sys.version)

sa_name = sys.argv[1]
sa_key = sys.argv[2]

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


# Create the BlockBlockService that is used to call the Blob service for the storage account
block_blob_service = BlockBlobService(account_name=sa_name, account_key=sa_key) 

# Create a container called 'quickstartblobs'.
# container_name ='quickstartblobs'
container_name = "{}-files".format(socket.gethostname().lower())
block_blob_service.create_container(container_name) 

# Set the permission so the blobs are public.
block_blob_service.set_container_acl(container_name, public_access=PublicAccess.Container)



# Create a file in Documents to test the upload and download.
local_path=os.path.expanduser("~\Documents")
local_file_name ="QuickStart_" + str(uuid.uuid4()) + ".txt"
full_path_to_file =os.path.join(local_path, local_file_name)

# Write text to the file.
file = open(full_path_to_file,  'w')
file.write("Hello, World!")
file.close()

print("Temp file = " + full_path_to_file)
print("\nUploading to Blob storage as blob" + local_file_name)

# Upload the created file, use local_file_name for the blob name
block_blob_service.create_blob_from_path(container_name, local_file_name, full_path_to_file)



# List the blobs in the container
print("\nList blobs in the container")
generator = block_blob_service.list_blobs(container_name)
for blob in generator:
    print("\t Blob name: " + blob.name)