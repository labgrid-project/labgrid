import os
import subprocess

import attr
from labgrid.driver.common import Driver
from labgrid.factory import target_factory
from labgrid.step import step
from labgrid.util.helper import processwrapper
from labgrid.var_dict import get_var

@target_factory.reg_driver
@attr.s(eq=False)
class UBootProviderDriver(Driver):
    """UBootProviderDriver - Build U-Boot image for a board

    Attributes:
        board (str): U-Boot board name, e.g. "gurnard"
        bl31 (str): pathname of ARM Trusted Firmware BL31 binary blob
        tee (str): pathname of OP-TEE Trusted Execution Environment blob
        binman_indir (str): pathname to a directory containing blobs for Binman
        board_extra (str): U-Boot board name for a second build which uses the
            same source code, e.g. "am62x_beagleplay_r5"

    Variables:
        commit (str): Optional commit to build (branch name, tag or hash)
        patch (str): Optional file containing a patch to apply
        use-board (str): Optional board to build, instead of the normal one
            specified in the environment file
        use-board-extra (str): Optional extra board to build, instead of the
            normal one specified in the environment file
        do-clean (str): If set to "1" this cleans the build before starting,
            otherwise it does an incremental build
        build-dir (str): If set, this is used as the build directory for U-Boot
        process-limit (int): Limits the number of buildman processes which can
            be running jobs at once. Set this to 1 to avoid over-taxing your
            CPU. Buildman does its own multithreading, so each process will use
            all available CPUs anyway.

    Paths (environment configuration):
        uboot_build_base: Base output directory for build, e.g. "/tmp/b".
            The build will taken place in build_base/<board>, e.g.
            "/tmp/b/gurnard"
        uboot_workdirs (str): Base directory to hold the git work directories,
            e.g. '/tmp/b/workdirs'. Each board's source code is staged in a
            subdirectory of this. This path is only needed if a commit is
            provided to be cherry-picked onto the main source tree.
        uboot_source (str): Directory of the main git tree containing the U-Boot
            source, e.g. '/home/fred/u-boot'

    Environment:
        U_BOOT_BUILD_DIR (str): If present, this is used as the build directory
            for U-Boot, otherwise the directory <uboot_build_base>/<board> is
            used
        U_BOOT_SOURCE_DIR (str): If present, this is used as a source directory
            for U-Boot, otherwise uboot_source is used, unless a commit is
            provided, in which case a workdir is used (see uboot_workdirs)

    """
    board = attr.ib(validator=attr.validators.instance_of(str))
    bl31 = attr.ib(default='', validator=attr.validators.instance_of(str))
    tee = attr.ib(default='', validator=attr.validators.instance_of(str))
    binman_indir = attr.ib(default='', validator=attr.validators.instance_of(str))
    board_extra = attr.ib(default='', validator=attr.validators.instance_of(str))

    def __attrs_post_init__(self):
        super().__attrs_post_init__()
        env = self.target.env
        if env:
            self.tool = env.config.get_tool('buildman')
        else:
            self.tool = 'buildman'
        self.build_base = env.config.get_path('uboot_build_base')
        self.workdirs = env.config.get_path('uboot_workdirs')
        self.sourcedir = env.config.get_path('uboot_source')

    def get_build_paths(self, boards=None):
        '''Get the paths to use for building the boards

        Both the normal build and the optional 'extra' build are returned.

        Args:
            board (list of str): Name of U-Boot boards to set up, or None for
                default

        Returns:
            list of str: List of pathnames for each build (main one first,
                optional 'extra' one second)
        '''
        pathname = get_var('build-dir')
        if pathname:
            return pathname, get_var('build-dir-extra')

        pathname = os.getenv('U_BOOT_BUILD_DIR')
        if pathname:
            return pathname, os.getenv('U_BOOT_BUILD_DIR_EXTRA')
        if not boards:
            boards = self.get_boards()
        return [os.path.join(self.build_base, b) for b in boards]

    def _get_source_path(self):
        """Get the path to the source code to build

        There is only one source path, even if two boards are being built.

        Returns:
            tuple:
                str: Path to source directory
                str: Description of directory, e.g. "in sourcedir"
        """
        # If we have a commit, use a worktree. Otherwise we just use the source
        # in the current directory
        pathname = os.getenv('U_BOOT_SOURCE_DIR')
        if pathname:
            return pathname, 'in pytest-source dir'
        return self.sourcedir, 'in sourcedir'

    def get_boards(self):
        """Get the board(s) to be built

        Returns:
            list of str: Names of U-Boot boards to set up (main one first,
                optional 'extra' one second)
        """
        boards = [get_var('use-board', self.board)]
        extra = get_var('use-board-extra', self.board_extra)
        if extra:
            boards.append(extra)
        return boards

    def run_build(self, board, build_path, do_print, detail, cwd, env, cmd_in):
        """Run a build for a single board

        Args:
            board (str): Name of U-Boot boards to build
            build_path (str): Path to use for the build output
            do_print )bool): True to print build message
            detail (str): Detail string to show to the user before building
            cwd (str): Current working-directory to set (contains source code)
            env (dict of str): Environment to use for the build
            cmd_in (list of str): Base arguments for buildman

        Raises:
            CalledProcessError if a build error happens
            ValueError if the build indicates it is non-functional due to
                missing blobs
        """
        cmd = cmd_in + ['--board', board, '-o', build_path]

        if do_print:
            print(f'Building U-Boot {detail} for {board}')
        self.logger.debug('cwd:%s cmd:%s', os.getcwd(), cmd)
        try:
            out = processwrapper.check_output(cmd + ['--fallback-mrproper'],
                                              cwd=cwd, env=env)
        except subprocess.CalledProcessError as exc:
            if b'--fallback-mrproper' in exc.stdout:
                try:
                    out = processwrapper.check_output(cmd + ['-m'], cwd=cwd,
                                                      env=env)
                except subprocess.CalledProcessError:
                    raise
            else:
                raise
        out = out.decode('utf-8', errors='ignore')
        fail = None
        for line in out.splitlines():
            if 'is non-functional' in line:
                fail = line
            self.logger.debug(line)
        if fail:
            raise ValueError(f'build failed: {fail}')

    @Driver.check_active
    @step(title='build')
    def build(self, do_print=True, config_only=False):
        """Builds U-Boot

        Performs an incremental build of U-Boot for the selected boards,
        returning a single output file produced by the build

        Returns:
            str: Path of build result, e.g. '/tmp/b/orangepi_pc'
        """
        boards = self.get_boards()
        build_paths = self.get_build_paths(boards)
        commit = get_var('commit')
        patch = get_var('patch')
        process_limit = get_var('process-limit')

        env = os.environ
        if self.bl31:
            env['BL31'] = self.bl31
        if self.binman_indir:
            env['BINMAN_INDIRS'] = self.binman_indir
        if self.tee:
            env['TEE'] = self.tee

        # Build the basic buildman args; --build is added later
        cmd = [
            self.tool,
            '-w',
            '-W',
            '-ve',
        ]
        if config_only:
            cmd.append('--config-only')
        if process_limit:
            cmd += ['--process-limit', process_limit]

        cwd, detail = self._get_source_path()

        # Select a commit and apply a patch if needed. There is only one source
        # tree so the first board is used
        workdir = None
        if commit:
            workdir = self._setup_worktree(boards[0], commit)
            cwd = workdir
            detail = 'in workdir'
            if patch:
                self._apply_patch(workdir, patch)
                detail += ' with patch'

        if get_var('do-clean', '0') == '1':
            cmd.append('-m')

        for board, build_path in zip(boards, build_paths):
            self.run_build(board, build_path, do_print, detail, cwd, env, cmd)

        return build_paths

    def _setup_worktree(self, board, commit):
        """Make sure there is a worktree for the current board

        If the worktree directory does not exist, it is created

        Args:
            board (str): Name of U-Boot board to set up
            commit (str): Commit to check out (hash or branch name)

        Returns:
            str: work directory for this board
        """
        workdir = os.path.join(self.workdirs, board)
        if not os.path.exists(workdir):
            cmd = [
                'git',
                '--git-dir', self.source_dir,
                'worktree',
                'add',
                board,
                '--detach',
            ]
            self.logger.info('Setting up worktree in %s', workdir)
            processwrapper.check_output(cmd, cwd=self.workdirs)
        else:
            cmd = [
                'git',
                '-C', workdir,
                'reset',
                '--hard',
            ]
            self.logger.info('Resetting worktree in %s', workdir)
            processwrapper.check_output(cmd, cwd=self.workdirs)

        self._select_commit(board, commit)
        return workdir

    def _select_commit(self, board, commit):
        """Select a particular commit in the worktree

        Args:
            board (str): Name of U-Boot board to set up
            commit (str): Commit to select (hash or branch name)
        """
        workdir = os.path.join(self.workdirs, board)
        cmd = [
            'git',
            '-C', workdir,
            'checkout',
            commit,
        ]
        self.logger.info('Checking out %s', commit)
        processwrapper.check_output(cmd)

    def _apply_patch(self, workdir, patch):
        """Apply a patch to the workdir

        Apply the patch. If something goes wrong,

        """
        cmd = [
            'git',
            '-C', workdir,
            'apply',
            patch,
        ]
        self.logger.info('Applying patch %s', patch)
        try:
            processwrapper.check_output(cmd)
        except:
            cmd = [
                'git',
                '-C', workdir,
                "am",
                '--abort',
            ]
            processwrapper.check_output(cmd)
            raise

    def query_info(self, name):
        boards = self.get_boards()
        if name == 'board':
            return boards[0]
        if name == 'board_extra':
            return boards[1] if len(boards) > 1 else None
        elif name == 'build_dir':
            return self.get_build_paths(boards)[0]
        elif name == 'build_dir_extra':
            paths = self.get_build_paths(boards)
            return paths[1] if len(paths) > 1 else None
        elif name == 'source_dir':
            return self._get_source_path()[0]
        elif name == 'config_file':
            build_path = self.build(do_print=False, config_only=True)[0]
            return os.path.join(build_path, '.config')
        return None
