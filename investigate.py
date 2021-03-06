"""Collects troubleshooting data and publishes it to an Azure Storage Account

:param storage-account-name: The name of the storage account to which the artifacts will be published
:type storage-account-name: str
:param key: The key that provides access to the storage account specified in arg[1]
:param key: str
:param cloud: The cloud environment in which the storage account exists.  Default is AzureCloud.  Valid values
              are AzureCloud and AzureUSGovernment
:param cloud: str
:returns: None
:rtype: None

v0.2.0
"""

import argparse
import os
import re
import subprocess
import gzip
import shutil
import socket
import tempfile
from collections import namedtuple
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


def write_messages_to_tmp(messages_path):
    shutil.copyfile(messages_path, get_messages_tmp_path())


def gettmp():
    return tempfile.gettempdir()


def get_subject_container_name():
    return "{}-files".format(
        socket.gethostname().lower().split('.')[0].replace('_', '-'))


def get_messages_archive_path():
    return os.path.join(gettmp(), 'messages_archive.txt.gz')


def get_messages_tmp_path():
    return os.path.join(gettmp(), 'messages')


def get_kernels_archive_path():
    return os.path.join(gettmp(), 'kernels.txt')


def find_boot_sdc(sdc_devices):
    for sdc in sdc_devices:
        mnt_path = os.path.join('/mnt', sdc)
        boot_path = os.path.join(mnt_path, 'grub2')

        if os.path.exists(boot_path):
            print("Found boot partition at: {}".format(mnt_path))
            return mnt_path


def get_kernels_in_boot(boot_path):
    kernels = [x for x in os.listdir(boot_path) if re.match('vmlinuz', x)]
    kernel_dict_list = []

    for kernel in kernels:
        kernel_path = os.path.join(boot_path, kernel)
        kernel_ctime = os.path.getctime(kernel_path)
        kernel_time = time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(kernel_ctime))
        kernel_dict_list.append({
            'kernel_name': kernel,
            'creation_date': kernel_time})

    sorted_kernel_list = sorted(kernel_dict_list, key=lambda x: x['creation_date'], reverse=True)

    return sorted_kernel_list


def write_kernels_in_boot(kernels):
    with open(get_kernels_archive_path(), 'w') as f_in:
        for kernel in kernels:
            f_in.write("{} : {}".format(
                kernel.get('kernel_name'),
                kernel.get('creation_date')))
            f_in.write('\n')


def create_storage_container(block_blob_service):
    container_gen = block_blob_service.list_containers()
    containers = [c.name for c in container_gen]
    subject_container_name = get_subject_container_name()

    if subject_container_name not in containers:
        print('Creating container {} in storage account {}'.format(subject_container_name,
                                                                   block_blob_service.account_name))
        block_blob_service.create_container(subject_container_name)
    else:
        print('Container: {} already exists'.format(subject_container_name))


def get_grub_cfg_files(boot_sdc):
    return [x for x in os.listdir(os.path.join(boot_sdc, 'grub2')) if re.match('grub.cfg', x)]


def get_grub_tmp_paths():
    tmp = os.path.join(gettmp(), 'grub')
    return [os.path.join(tmp, x) for x in os.listdir(tmp) if re.match('grub.cfg', x)]


def copy_grub_cfg_files(boot_sdc):
    grub_files = get_grub_cfg_files(boot_sdc)
    grub_temp_root = os.path.join(gettmp(), 'grub')

    if not os.path.exists(grub_temp_root):
        os.mkdir(grub_temp_root)

    for gfile in grub_files:
        full_path = os.path.join(boot_sdc, 'grub2', gfile)
        shutil.copyfile(full_path, os.path.join(gettmp(), 'grub', gfile))


def get_azure_log_tmp():
    return os.path.join(gettmp(), 'azure_logs', 'waagent.log')


def find_azure_log(sdc_devices):
    for sdc in sdc_devices:
        mnt_path = os.path.join('/mnt', sdc)
        azure_log_temp = os.path.join(mnt_path, 'var', 'log', 'waagent.log')

        if os.path.exists(azure_log_temp):
            return azure_log_temp


def copy_azure_log_to_tmp(azure_log):
    azure_tmp_full = get_azure_log_tmp()
    azure_tmp_dir, _ = os.path.split(azure_tmp_full)

    if not os.path.exists(azure_tmp_dir):
        os.mkdir(azure_tmp_dir)

    shutil.copyfile(azure_log, azure_tmp_full)


def get_blobs_to_upload():
    Blob = namedtuple('Blob', 'name, file')
    fdate = dt.utcnow().strftime('%Y%m%d')

    blob_list = [
        Blob("messages-gzip-{}".format(fdate), get_messages_archive_path()),
        Blob("kernel-list-{}".format(fdate), get_kernels_archive_path()),
        Blob("messages-txt-{}".format(fdate), get_messages_tmp_path()),
        Blob("waagent-log-{}".format(fdate), get_azure_log_tmp()),
        Blob("hit-errors-{}".format(fdate), get_hits_file()),
    ]

    grub_tmp_files = get_grub_tmp_paths()

    for gfile in grub_tmp_files:
        _, filename = os.path.split(gfile)
        ffilename = filename.replace('.', '-')
        blob_list.append(Blob(ffilename, gfile))

    return blob_list


def upload_blobs(block_blob_service):
    blobs_to_upload = get_blobs_to_upload()
    subject_container_name = get_subject_container_name()
    blob_gen = block_blob_service.list_blobs(subject_container_name)
    blobs = [b.name for b in blob_gen]

    for blob in blobs_to_upload:
        if blob.name not in blobs:
            print('Creating blob, {}, in container, {}'.format(blob.name, subject_container_name))
            block_blob_service.create_blob_from_path(
                container_name=subject_container_name,
                blob_name=blob.name,
                file_path=blob.file)
        else:
            print('Blob: {} is already in container ({})'.format(blob.name, subject_container_name))


def get_endpoint_suffix(cloud):
    if cloud.lower() == 'azureusgovernment':
        return 'core.usgovcloudapi.net'
    elif cloud.lower() == 'azurecloud':
        return 'core.windows.net'

    return None


def search_messages_for_errors(messages_path):
    Hit = namedtuple('Hit', 'line_number, line_text')
    hits = []

    matchers = [
        r'(.*)Kernel panic',
        r'(.*)unable to handle kernel NULL pointer',
        r'(.*)task swapper:.* blocked for more',
        r'(.*)No root device'
    ]

    for matcher in matchers:
        print("Looking for matches with: {}".format(matcher))
        with open(messages_path, 'r') as fin:
            for line_num, line_text in enumerate(fin):
                match = re.match(matcher, line_text)
                if match:
                    print('Found a match at line #{}'.format(line_num))
                    print('Line found: {}'.format(line_text))
                    print
                    hits.append(Hit(line_num, line_text))
            
    return hits


def get_hits_file():
    return os.path.join(gettmp(), 'hits.txt')    


def write_hits_to_file(hits):
    with open(get_hits_file(), 'w') as fout:
        fout.write('Hits found in Messages\n\n')
        if not hits:
            print('No hits found')
            fout.write('No hits found\n')
        for hit in hits:
            fout.write('Line Number: {}\nLine Text: {}\n\n'.format(hit.line_number,
                                                                   unicode(hit.line_text, errors='ignore')))


def pargs():
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--storage-account-name', help='Provide the name of the storage account', required=True)
    parser.add_argument('-k', '--key', help='Provide the storage account key', required=True)
    parser.add_argument('-c', '--cloud',
                        help='Provide the Cloud Environment of the storage account',
                        choices=('azureusgovernment', 'azurecloud'),
                        type=str.lower,
                        default='AzureCloud')
    parser.add_argument('-v', '--verbose', action='store_true', help='Get verbose output from the cmd')

    args = parser.parse_args()
    sa_name = args.storage_account_name
    sa_key = args.key
    cloud = args.cloud
    verbose = args.verbose

    return sa_name, sa_key, cloud, verbose


def print_verbose(enabled, msg):
    if enabled:
        print(msg)


def main():
    sa_name, sa_key, cloud, verbose = pargs()
    cloud_endpoint = get_endpoint_suffix(cloud)

    print_verbose(verbose, "Args provided: {}, {}, {}, {}".format(
        sa_name,
        sa_key,
        cloud,
        verbose
    ))
    print_verbose(verbose, "Will use storage endpoint suffix: {}".format(cloud_endpoint))

    sdc_devices = get_sdc_devices()
    print_verbose(verbose, "Found {} sdc devices: {}".format(len(sdc_devices), sdc_devices))
    mount_sdc_devices(sdc_devices)

    msg_path = find_messages(sdc_devices)
    archive_messages(msg_path)
    write_messages_to_tmp(msg_path)

    boot_sdc = find_boot_sdc(sdc_devices)
    kernels = get_kernels_in_boot(boot_sdc)
    write_kernels_in_boot(kernels)

    copy_grub_cfg_files(boot_sdc)

    az_log = find_azure_log(sdc_devices)
    copy_azure_log_to_tmp(az_log)

    hits = search_messages_for_errors(msg_path)
    write_hits_to_file(hits)

    block_blob_service = BlockBlobService(account_name=sa_name, account_key=sa_key, endpoint_suffix=cloud_endpoint)

    print_verbose(verbose, "Creating the storage container: {}".format(get_subject_container_name()))
    create_storage_container(block_blob_service)
    print_verbose(verbose, "Uploading blobs to container")

    upload_blobs(block_blob_service)


if __name__ == '__main__':
    main()
