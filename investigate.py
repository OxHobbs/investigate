"""Collects troubleshooting data and publishes it to an Azure Storage Account

:param storage-account-name: The name of the storage account to which the artifacts will be published
:type storage-account-name: str
:param access-key: The key that provides access to the storage account specifed in arg[1]
:param access-key: str
:returns: None
:rtype: None

v0.2.0
"""


import sys
import os
import re
import subprocess
import gzip
import shutil
import socket
from datetime import datetime as dt
import time
from azure.storage.blob import BlockBlobService


def get_sdc_devices():
    return sorted([d for d in os.listdir('/dev') if re.match(r'sdc\d+', d)])


def mount_sdc_devices(sdc_devices):
    for sdc in sdc_devices:
        mnt_path = os.path.join('/mnt', sdc)

        if not os.path.exists(mnt_path):
            os.mkdir(mnt_path)

        if not os.path.ismount(mnt_path):
            print("Mounting {} to {}".format(sdc, mnt_path))
            subprocess.call(['mount', os.path.join('/dev', sdc), mnt_path])
        else:
            print("{} is ALREADY mounted at {}".format(sdc, mnt_path))


def find_messages(sdc_devices):
    for sdc in sdc_devices:
        mnt_path = os.path.join('/mnt', sdc)
        messages_path = os.path.join(mnt_path, 'var', 'log', 'messages')

        if os.path.exists(messages_path):
            print('Found messages log in path: {}'.format(mnt_path))
            return messages_path


def archive_messages(messages_path):
    messages_arch_path = get_messages_archive_path()

    with open(messages_path, 'rb') as f_in, gzip.open(messages_arch_path, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)


def get_subject_container_name():
    return "{}-files".format(
        socket.gethostname().lower().replace('_', '-').replace('.', ''))


def get_messages_archive_path():
    return os.path.join('/tmp', 'messages_archive.txt.gz')


def create_storage_container(block_blob_service):
    container_gen = block_blob_service.list_containers()
    containers = [c.name for c in container_gen]
    subject_container_name = get_subject_container_name()

    if subject_container_name not in containers:
        print('Creating container {} in storage account {}'.format(subject_container_name, block_blob_service.account_name))
        block_blob_service.create_container(subject_container_name)
    else:
        print('Container: {} already exists'.format(subject_container_name))


def upload_blob(block_blob_service):
    blob_name = "messages-{}".format(dt.utcnow().strftime('%Y%m%d'))
    subject_container_name = get_subject_container_name()

    blob_gen = block_blob_service.list_blobs(subject_container_name)
    blobs = [b.name for b in blob_gen]

    if blob_name not in blobs:
        print('Creating blob, {}, in container, {}'.format(blob_name, subject_container_name))
        block_blob_service.create_blob_from_path(
            container_name=subject_container_name,
            blob_name=blob_name,
            file_path=get_messages_archive_path()
        )
    else:
        print('Blob: {} is already in container ({})'.format(blob_name, subject_container_name))


def main():
    sa_name = sys.argv[1]
    sa_key = sys.argv[2]

    sdc_devices = get_sdc_devices()
    mount_sdc_devices(sdc_devices)
    msg_path = find_messages(sdc_devices)
    archive_messages(msg_path)

    block_blob_service = BlockBlobService(account_name=sa_name, account_key=sa_key, endpoint_suffix='core.usgovcloudapi.net')
    create_storage_container(block_blob_service)
    upload_blob(block_blob_service)


if __name__ == '__main__':
    main()
