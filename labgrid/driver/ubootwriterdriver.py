import os
import pathlib
import time

import attr
from labgrid.driver.common import Driver
from labgrid.factory import target_factory
from labgrid.step import step

@target_factory.reg_driver
@attr.s(eq=False)
class UBootWriterDriver(Driver):
    """UBootWriterDriver - Write U-Boot image to a board

    Attributes:
        method (str): Writing method, indicating specifically how to write U-Boot
            to the board, e.g. "rpi3"
    """
    method = attr.ib(validator=attr.validators.instance_of(str))
    bl1 = attr.ib(default='', validator=attr.validators.instance_of(str))
    bl2 = attr.ib(default='', validator=attr.validators.instance_of(str))
    tzsw = attr.ib(default='', validator=attr.validators.instance_of(str))
    vbe_tpl = attr.ib(default='', validator=attr.validators.instance_of(str))

    bindings = {
        'storage': {'USBStorageDriver', None},
        'sdmux': {'USBSDWireDriver', None},
        'emul': {'SFEmulatorDriver', None},
        "qemu": {"QEMUDriver", None},
    }

    def __attrs_post_init__(self):
        super().__attrs_post_init__()

    @Driver.check_active
    @step(title='write')
    def write(self, image_dirs):
        """Writes U-Boot to the board

        Args:
            image_dirs (list of str): Directories containing the U-Boot output
                files for the build. If there is an extra build it is the second
                element
        """
        image_dir = image_dirs[0]
        print(f'Writing U-Boot using method {self.method}')
        if self.sdmux:
            self.target.activate(self.sdmux)
            self.sdmux.set_mode('host')

        if self.storage:
            self.target.activate(self.storage)

        image = os.path.join(image_dir, 'u-boot.bin')
        if self.method in ['rpi2', 'rpi0']:
            dest = pathlib.PurePath('/kernel.img')
            self.storage.write_files([image], dest, 1, False)
        elif self.method == 'rpi3':
            dest = pathlib.PurePath('/rpi3-u-boot.bin')
            self.storage.write_files([image], dest, 1, False)
        elif self.method in ['rpi4', 'rpi5']:
            dest = pathlib.PurePath('/u-boot.bin')
            self.storage.write_files([image], dest, 1, False)
        elif self.method == 'sunxi':
            image = os.path.join(image_dir, 'u-boot-sunxi-with-spl.bin')
            self.storage.write_image(image, seek=8, block_size=1024)
        elif self.method == 'rockchip':
            image = os.path.join(image_dir, 'u-boot-rockchip.bin')
            self.storage.write_image(image, seek=64)

            if self.vbe_tpl:
                image = os.path.join(image_dir, f'alt-{self.vbe_tpl}.bin')
                if os.path.exists(image):
                    self.storage.write_image(image, seek=64)
        elif self.method == 'em100':
            image = os.path.join(image_dir, 'u-boot.rom')
            self.emul.write_image(image)
        elif self.method == 'zynq':
            dest = pathlib.PurePath('/')
            spl = os.path.join(image_dir, 'spl/boot.bin')
            self.storage.write_files([spl], dest, 1, True)

            u_boot = os.path.join(image_dir, 'u-boot.img')
            self.storage.write_files([u_boot], dest, 1, True)
        elif self.method == 'zynqmp':
            dest = pathlib.PurePath('/')
            spl = os.path.join(image_dir, 'spl/boot.bin')
            self.storage.write_files([spl], dest, 1, True)

            u_boot = os.path.join(image_dir, 'u-boot.itb')
            self.storage.write_files([u_boot], dest, 1, True)
        elif self.method == 'bbb':
            u_boot = os.path.join(image_dir, 'u-boot.img')
            self.storage.write_image(u_boot, seek=1, block_size=384 << 10,
                                     count=4)
            mlo = os.path.join(image_dir, 'MLO')
            self.storage.write_image(mlo, seek=1, block_size=128 << 10,
                                     count=1)
        elif self.method == 'amlogic':
            image = os.path.join(image_dir, 'image.bin')
            self.storage.write_image(image, block_size=512)
        elif self.method == 'samsung':
            # Does not work on XU3
            self.storage.write_image(self.bl1, seek=1)
            self.storage.write_image(self.bl2, seek=31)
            self.storage.write_image(self.tzsw, seek=2111)
            self.storage.write_image(image, seek=63)
        elif self.method == 'qemu-rom':
            rom = os.path.join(image_dir, 'u-boot.rom')
            self.qemu.set_bios(rom)
        elif self.method == 'qemu':
            rom = os.path.join(image_dir, 'u-boot.bin')
            self.qemu.set_bios(rom)
        elif self.method == 'ti,am625':
            r5_dest = pathlib.PurePath('/tiboot3.bin')
            r5_image = os.path.join(image_dirs[1], 'tiboot3-am62x-gp-evm.bin')
            self.storage.write_files([r5_image], r5_dest, 1, False)

            spl_dest = pathlib.PurePath('/tispl.bin')
            spl_image = os.path.join(image_dir, 'tispl.bin_unsigned')
            self.storage.write_files([spl_image], spl_dest, 1, False)

            dest = pathlib.PurePath('/u-boot.img')
            image = os.path.join(image_dir, 'u-boot.img_unsigned')
            self.storage.write_files([image], dest, 1, False)
        elif self.method == 'riscv':
            spl = os.path.join(image_dir, 'spl/u-boot-spl.bin.normal.out')
            self.storage.write_image(spl, partition=13, block_size=512)

            u_boot = os.path.join(image_dir, 'u-boot.itb')
            self.storage.write_image(u_boot, partition=2, block_size=512)
        elif self.method == 'mx6':
            img = os.path.join(image_dir, 'u-boot-with-spl.imx')
            self.storage.write_image(img, seek=1, block_size=1024)
        else:
            raise ValueError(f'Unknown writing method {self.method}')
        if self.storage:
            self.target.deactivate(self.storage)
        if self.sdmux:
            # Provide time for the dd 'sync' to complete
            time.sleep(1)
            self.sdmux.set_mode('dut')

    @Driver.check_active
    @step(title='prepare_boot')
    def prepare_boot(self):
        if self.sdmux:
            self.sdmux.set_mode("dut")

    @Driver.check_active
    @step(title='send')
    def send(self, image_dirs):
        """Sends U-Boot to the board over USB

        Args:
            image_dirs (list of str): Directories containing the U-Boot output
                files for the build. If there is an extra build it is the second
                element
        """
        # For now we only support a single image_dir
        image_dir = image_dirs[0]
        print(f'Sending U-Boot using method {self.method}')
        u_boot = os.path.join(image_dir, 'u-boot.bin')
        if self.method == 'sunxi':
            sender = self.target.get_driver('SunxiUSBDriver')
            spl = os.path.join(image_dir, 'spl/sunxi-spl.bin')
            print('- Send SPL')
            sender.load(spl, 'spl')
        elif self.method == 'tegra':
            sender = self.target.get_driver('TegraUSBDriver')
            u_boot = os.path.join(image_dir, 'u-boot-dtb-tegra.bin')
        elif self.method == 'samsung':
            sender = self.target.get_driver('SamsungUSBDriver')
            print('- Send BL1')
            sender.load(None, 'bl1')

            spl = os.path.join(image_dir, 'spl/u-boot-spl.bin')
            print('- Send SPL')
            sender.load(spl, 'spl')
        elif self.method == 'uuu-imx':
            sender = self.target.get_driver('UUUDriver')
            imx = os.path.join(image_dir, 'u-boot-dtb.imx')
            print('- Send U-Boot')
            sender.load(imx)
            return
        else:
            raise ValueError(f'Unknown sending method {self.method}')

        print('- Send U-Boot')
        sender.load(u_boot)
        sender.execute()
