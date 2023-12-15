
import subprocess

def get_uname_machine():
    
    # translate `uname -m` output to debian/ubuntu architecture terms
    uname_translate = {
        "x86_64": "amd64"
    }
    # default: use `uname -m`
    architecture = subprocess.check_output(["uname","-m"]).decode("utf-8").rstrip()
    architecture = uname_translate.get(architecture, architecture)

    # check ELF header - inspired by /proc/sys/fs/binfmt_misc/qemu-*
    # Why? e.g. a AARCH64 Kernel can run a armhf userspace (buzzword: Raspian OS)
    binfmt = {
        "arm":     (b'\x7f\x45\x4c\x46\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00' # e_ident
                    b'\x02\x00\x28\x00'                                                 # e_type + e_machine
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' # e_<version,entry,phoff,shoff>
                    b'\x00\x00\x00\x00',                                                # e_flags
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00'),
        "armhf":   (b'\x7f\x45\x4c\x46\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\x28\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x04\x00'),
        "aarch64": (b'\x7f\x45\x4c\x46\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\xb7\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'),
        "amd64":   (b'\x7f\x45\x4c\x46\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x02\x00\x3e\x00',
                    b'\xff\xff\xff\xff\xff\xff\xff\x00\xff\xff\xff\xff\xff\xff\xff\xff'
                    b'\xfe\xff\xff\xff'),
    }

    elfheader = b''
    with open("/proc/self/exe", "rb") as exe:
        elfheader = exe.read(40)
    for arch, compare in binfmt.items():
        magic = compare[0]
        mask = compare[1]

        match = True
        for i in range(min(len(elfheader),len(magic),len(mask))):
            match = match and ((elfheader[i] & mask[i]) == magic[i])

        if match:
            architecture=arch
            break

    return architecture

methods = {
    'get_uname_machine': get_uname_machine
}