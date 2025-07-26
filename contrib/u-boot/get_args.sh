#!/bin/bash

# Decode arguments
# This decodes and removes the flags and the target argument
# It returns with the next argument in $1

# Usage
# . get_arg.sh
#
# The allowed_args variable must be set to the list of valid args for this
# script, e.g. "cnstv"

export build_adjust=

# 1 to bootstrap the board, i.e. write U-Boot to it and start it up
export bootstrap=1

# 1 to build U-Boot, else the existing build will be used
export build=1

# 1 to clean the build directory before starting the build
export clean=0

# -v to show variables and use verbose mode in Labgrid
export V=

# 1 to bootstrap over USB using the boot ROM
export send=0

# 1 to reset the board before connecting
export reset=1

# selects the target strategy-state to use, in Labgrid's UBootStrategy
export strategy="-s start -e off"

# --use-running-system to tell pytest not to wait for a U-Boot prompt
export use_running_system=
export lg_use_running_system=

# build path to use (empty to use default)
export build_dir=

# extra build path to use (empty to use default)
export build_dir_extra=

# limit the number of active buildman processors
export process_limit=2

# debug flag for labgrid
export debug=

# console log file
export console_log=
export lg_console_log=

# console listen-only
export listen_only=

# set EM100-Pro into trace mode and write to a file
export em100_trace=

# log file for internal Labgrid logging (not the board's console)
export log_output=
export lg_log_output=

while getopts "${allowed_args}" opt; do
	case $opt in
	a )
	  build_adjust+=":$OPTARG"
	  ;;
	d )
	  build_dir="$OPTARG"
	  ;;
	D )
	  debug=-d
	  ;;
	c )
	  clean=1
	  ;;
	B )
	  build=0
	  ;;
	e )
	  em100_trace="$OPTARG"
	  ;;
	h )
	  usage
	  ;;
	l )
	  console_log="--logfile $OPTARG"
	  lg_console_log="--lg-console-logfile $OPTARG"
	  ;;
	L )
	  listen_only="--listenonly"
	  ;;
	o )
	  log_output="--log-output $OPTARG"
	  lg_log_output="--lg_log-output $OPTARG"
	  ;;
	s )
	  send=1
	  ;;
	R )
	  reset=0
	  bootstrap=0
	  build=0
	  strategy=
	  use_running_system="--use-running-system"
	  lg_use_running_system="--lg-use-running-system"
	  ;;
	T )
	  bootstrap=0
	  build=0
	  ;;
	v )
	  V=-v
	  ;;
	x )
	  build_dir_extra="$OPTARG"
	  ;;
	\? )
	  echo "Invalid option: $OPTARG" 1>&2
	  exit 1
	  ;;
	esac
done

shift $((OPTIND -1))

target="$1"
shift

[[ -z "${target}" ]] && usage "Missing target"

# vars is passed to labgrid itself; these vars are parsed by UBootStrategy and
# UBootProvider
vars="-V do-bootstrap ${bootstrap} -V do-build ${build} -V do-clean ${clean}"
vars+=" -V do-send ${send} -V do-reset ${reset}"
[ -n "${em100_trace}" ] && vars+="-V em100-trace ${em100_trace}"

[ -n "${build_dir}" ] && vars+=" -V build-dir ${build_dir}"
[ -n "${build_dir_extra}" ] && vars+=" -V build-dir-extra ${build_dir_extra}"
[ -n "${build_adjust}" ] && vars+=" -V build-adjust ${build_adjust}"

# lg_vars is passed to Labgrid's pytest plugin
lg_vars="--lg-var do-bootstrap ${bootstrap} --lg-var do-build ${build}"
lg_vars+=" --lg-var do-clean ${clean} --lg-var do-send ${send}"
lg_vars+=" --lg-var do-reset ${reset}"
[ -n "${em100_trace}" ] && lg_vars+=" --lg-var em100-trace ${em100_trace}"

[ -n "${build_dir}" ] && lg_vars+=" --lg-var build-dir ${build_dir}"
[ -n "${build_dir_extra}" ] && lg_vars+=" --lg-var build-dir-extra ${build_dir_extra}"
[ -n "${build_adjust}" ] && lg_vars+=" --lg-var build-adjust ${build_adjust}"

export vars lg_vars target

# Note that the shell variables are exported through to pytest by ub-pyt,
# ub-smoke and ub-bisect and then through to the console.labgrid-sjg script
# which uses them to pass the values as variables to labgrid using the -V
# option

if [ -n "${V}" ]; then
	echo "vars: ${vars}"
	echo "lg_vars: ${lg_vars}"
fi
