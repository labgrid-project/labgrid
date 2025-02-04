# labgrid-client(1) completion                                                 -*- shell-script -*-

# options top level and subcommands support
_labgrid_shared_options="--help"
_labgrid_main_opts_with_value="@(-x|--coordinator|-c|--config|-p|--place|-s|--state|-i|--initial-state|-P|--proxy)"

# Parses labgrid-client arguments
# Sets arg to subcommand, excluding options and their values.
# Sets last_arg_opt_with_value to true if the last argument is an option requiring a value, else
# false.
# Sets base_cmd to the labgrid-client base command up to subcommand and removes trailing
# option requiring a value - useful to call 'labgrid-client complete' with place/coordinator/proxy set
# Before calling this function, make sure arg, base_cmd and last_arg_opt_with_value are local
_labgrid_parse_args()
{
    local i cmd_type
    arg=
    base_cmd=("${COMP_WORDS[0]}")
    last_arg_opt_with_value=false

    for ((i = 1; i < COMP_CWORD; i++)); do
        base_cmd+=( "$(dequote "${COMP_WORDS[i]}")" )

        # skip options
        if [[ ${COMP_WORDS[i]} == -* ]]; then
            # shellcheck disable=SC2053
            if [[ ${COMP_WORDS[i]} == $_labgrid_main_opts_with_value ]]; then
                if [[ "$((i+1))" == "$COMP_CWORD" ]]; then
                    last_arg_opt_with_value=true
                fi
            fi
            continue
        fi

        # skip option values
        # shellcheck disable=SC2053
        if [[ ${COMP_WORDS[i-1]} == $_labgrid_main_opts_with_value ]]; then
            continue
        fi

        # drop last command component, as we reached the subcommand
        unset 'base_cmd[-1]'

        arg="${COMP_WORDS[i]}"
        break
    done

    # drop incomplete option expecting a value
    if $last_arg_opt_with_value; then
        unset 'base_cmd[-1]'
    fi

    # resolve base command aliases
    if cmd_type=$(type -t -f "${base_cmd[0]}" 2>/dev/null); then
        if [[ "$cmd_type" == "alias" ]]; then
            base_cmd[0]="${BASH_ALIASES["${base_cmd[0]}"]}"
        fi
    fi
}

# Counts the number of arguments, excluding options and top level option values
# @param $1 glob additional options expecting a value
# Before calling this function, make sure args is local
_labgrid_count_args()
{
    local pattern

    if [ -n "$1" ]; then
        pattern="${_labgrid_main_opts_with_value::-1}|${1:2}"
    else
        pattern="$_labgrid_main_opts_with_value"
    fi

    _count_args "" "$pattern" || return
}

# Completes using 'labgrid-client complete'
# @param $1 type for 'labgrid-client complete'
# @param $2 cur as set by _init_completion
_labgrid_complete()
{
    local completion_type cur choices arg last_arg_opt_with_value base_cmd
    completion_type="$1"
    cur="$2"

    _labgrid_parse_args

    # TODO: handle completions including spaces
    if ! choices=$("${base_cmd[@]}" complete "$completion_type" 2>/dev/null); then
        return
    fi

    COMPREPLY=( $(compgen -W "$choices" -- "$cur") )
}

# Completes exporters exporting available resources
# @param $1 cur as set by _init_completion
_labgrid_complete_exporters()
{
    local cur resources exporters arg last_arg_opt_with_value base_cmd
    cur="$1"

    _labgrid_parse_args

    if ! resources=$("${base_cmd[@]}" complete resources 2>/dev/null); then
        return
    fi

    exporters=$(cut -d/ -f1 <<< "$resources" | uniq)
    COMPREPLY=( $(compgen -W "$exporters" -- "$cur") )
}

# Completes subcommand options
# @param $1 array with additional options
_labgrid_client_generic_subcommand() {
    local cur prev words cword
    _init_completion || return

    case "$cur" in
    -*)
        local options="$1 $_labgrid_shared_options"
        COMPREPLY=( $(compgen -W "$options" -- "$cur") )
        ;;
    esac
}

##############################
# subcommand functions below #
##############################

_labgrid_client_resources()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -e|--exporter)
        _labgrid_complete_exporters "$cur"
        return
        ;;
    esac

    case "${cur}" in
    -*)
        local options="--acquired \
                       --exporter \
                       --sort-by-matched-place-change \
                       $_labgrid_shared_options"
        COMPREPLY=( $(compgen -W "$options" -- "$cur") )
        ;;
    *)
        _labgrid_complete resources "$cur"
        ;;
    esac
}

_labgrid_client_r()
{
    _labgrid_client_resources
}

_labgrid_client_places()
{
    _labgrid_client_generic_subcommand "--acquired --released --sort-last-changed"
}

_labgrid_client_p()
{
    _labgrid_client_places
}

_labgrid_client_who()
{
    _labgrid_client_generic_subcommand "--show-exporters"
}

_labgrid_client_add_match()
{
    local cur prev words cword
    _init_completion || return

    case "${cur}" in
    -*)
        COMPREPLY=( $(compgen -W "$_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        _labgrid_complete resources "$cur"
        ;;
    esac
}

_labgrid_client_del_match()
{
    local cur prev words cword
    _init_completion || return

    case "${cur}" in
    -*)
        COMPREPLY=( $(compgen -W "$_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        _labgrid_complete matches "$cur"
        ;;
    esac
}

_labgrid_client_add_named_match()
{
    local cur prev words cword
    _init_completion || return

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "$_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _labgrid_complete resources
        return
        ;;
    esac
}

_labgrid_client_acquire()
{
    _labgrid_client_generic_subcommand "--allow-unmatched"
}

_labgrid_client_lock()
{
    _labgrid_client_acquire
}

_labgrid_client_release()
{
    _labgrid_client_generic_subcommand "--kick"
}

_labgrid_client_unlock()
{
    _labgrid_client_release
}

_labgrid_client_release_from()
{
    local args cur prev words cword
    _init_completion || return

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "$_labgrid_shared_options" -- "$cur") )
        ;;
    */*)
        _labgrid_count_args || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        COMPREPLY=( $(compgen -A user -P "${cur%%/*}/" -- "${cur##*/}") )
        ;;
    *)
        _labgrid_count_args || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        compopt -o nospace
        # -c for colon suffix
        _known_hosts_real -c -- "$cur" || return
        # replace colon suffix with "/" suffix
        COMPREPLY=( $(sed -E 's#:( |$)#/\1#g' <<< "${COMPREPLY[@]}") )
        # drop hosts containing dots or colons
        COMPREPLY=( ${COMPREPLY[@]//*[.:]*/} )
        ;;
    esac
}

_labgrid_client_allow()
{
    _labgrid_client_release_from
}

_labgrid_client_power()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -t|--delay)
        return
        ;;
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--delay --name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-t|--delay)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        COMPREPLY=( $(compgen -W "on off cycle get" -- "$cur") )
        ;;
    esac
}

_labgrid_client_pw()
{
    _labgrid_client_power
}

_labgrid_client_io()
{
    local cur prev words cword
    _init_completion || return

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "$_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args || return
        # only complete second argument
        case "$args" in
        2)
            COMPREPLY=( $(compgen -W "high low get" -- "$cur") )
            ;;
        3)
            _labgrid_complete match-names "$cur"
            ;;
        esac
        ;;
    esac
}

_labgrid_client_console()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    --logfile)
        _filedir
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--listenonly --loop --logfile $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _labgrid_complete match-names "$cur"
    esac
}

_labgrid_client_con()
{
    _labgrid_client_console
}

_labgrid_client_dfu()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    --wait)
        return
        ;;
    download|detach|list)
        _filedir
        ;;
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--wait --name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(--wait|-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        COMPREPLY=( $(compgen -W "download detach list" -- "$cur") )
        ;;
    esac
}

_labgrid_client_fastboot()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    --wait)
        return
        ;;
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--wait --name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        _filedir
        ;;
    esac
}

_labgrid_client_flashscript()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _filedir
        ;;
    esac
}

_labgrid_client_bootstrap()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -w|--wait)
        return
        ;;
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--wait --name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-w|--wait|-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _filedir
        ;;
    esac
}

_labgrid_client_sd_mux()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        COMPREPLY=( $(compgen -W "dut host off client get" -- "$cur") )
        ;;
    esac
}

_labgrid_client_usb_mux()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args actions
        _labgrid_count_args "@(-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        actions="off \
                 dut-device \
                 host-dut \
                 host-device \
                 host-dut+host-device"
        COMPREPLY=( $(compgen -W "$actions") )
        ;;
    esac
}

_labgrid_client_ssh()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    esac
}

_labgrid_client_scp()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-n|--name)" || return
        # only complete second and third argument
        if [ "$args" -lt 2 ] || [ "$args" -gt 3 ]; then
            return
        fi

        _filedir
        ;;
    esac
}

_labgrid_client_rsync()
{
    _labgrid_client_scp
}

_labgrid_client_sshfs()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-n|--name)" || return
        # only complete third argument
        [ "$args" -ne 3 ] && return

        _filedir -d
        ;;
    esac
}

_labgrid_client_forward()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name --local --remote $_labgrid_shared_options" -- "$cur") )
        ;;
    esac
}

_labgrid_client_video()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--quality --controls --name $_labgrid_shared_options" -- "$cur") )
        ;;
    esac
}

_labgrid_client_audio()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        ;;
    esac
}

_labgrid_client_tmc()
{
    local args cur prev words cword
    _init_completion || return

    case "$prev" in
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        COMPREPLY=( $(compgen -W "--name $_labgrid_shared_options" -- "$cur") )
        return
        ;;
    *)
        local args
        _labgrid_count_args "@(-n|--name)" || return
        # only complete second argument
        if [ "$args" -eq 2 ]; then
            COMPREPLY=( $(compgen -W "cmd query screen channel" -- "$cur") )
            return
        fi
        ;;
    esac

    _labgrid_count_args || return
    [ "$args" -lt 3 ] && return

    case "$prev" in
    screen)
        COMPREPLY=( $(compgen -W "show save" -- "$cur") )
        return
        ;;
    esac

    if [[ "${COMP_WORDS[COMP_CWORD-2]}" == "channel" ]]; then
        COMPREPLY=( $(compgen -W "info values" -- "$cur") )
        return
    fi
}

_labgrid_client_write_image()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -w|--wait)
        ;&
    -p|--partition)
        ;&
    --skip)
        ;&
    --seek)
        return
        ;;
    --mode)
        COMPREPLY=( $( compgen -W "dd bmaptool" -- "$cur") )
        return
        ;;
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        local options="--wait --partition --skip --seek --mode --name $_labgrid_shared_options"
        COMPREPLY=( $(compgen -W "$options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-w|--wait|-p|--partition|--skip|--seek|--mode|-n|--name)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _filedir
        ;;
    esac
}

_labgrid_client_write_files()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    -w|--wait)
        ;&
    -p|--partition)
        ;&
    -t|--target-directory)
        ;&
    -T)
        ;&
    -n|--name)
        _labgrid_complete match-names "$cur"
        return
        ;;
    esac

    case "$cur" in
    -*)
        local options="--wait --partition --target-directory --name $_labgrid_shared_options"
        COMPREPLY=( $(compgen -W "$options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(-w|--wait|-p|--partition|-t|--target-directory|-T|-n|--name)" || return

        _filedir
        ;;
    esac
}

_labgrid_client_reserve()
{
    _labgrid_client_generic_subcommand "--wait --shell --prio"
}

_labgrid_client_export()
{
    local cur prev words cword
    _init_completion || return

    case "$prev" in
    --format)
        COMPREPLY=( $( compgen -W "shell shell-export json" -- "$cur" ) )
        return
        ;;
    esac

    case "$cur" in
    -*)
        local options="--format $_labgrid_shared_options"
        COMPREPLY=( $(compgen -W "$options" -- "$cur") )
        ;;
    *)
        local args
        _labgrid_count_args "@(--format)" || return
        # only complete second argument
        [ "$args" -ne 2 ] && return

        _filedir
        ;;
    esac
}

# main entry point
_labgrid_client()
{
    local arg cur prev words cword base_cmd last_arg_opt_with_value

    # require bash-completion with _init_completion
    type -t _init_completion >/dev/null 2>&1 || return

    _init_completion || return
    _labgrid_parse_args

    COMPREPLY=()

    # no top level subcommand found
    if [ -z "$arg" ]; then
        # complete top level option values
        if $last_arg_opt_with_value; then
            case "$prev" in
            -c|--config)
                _filedir
                ;;
            -p|--place)
                _labgrid_complete places "$cur"
                ;;
            esac
            return
        fi

        case "$cur" in
        --*)
            # top level args completion
            local options="--coordinator \
                           --config \
                           --place \
                           --state \
                           --initial-state \
                           --debug \
                           --verbose \
                           --proxy \
                           $_labgrid_shared_options"

            COMPREPLY=( $(compgen -W "$options" -- "$cur" ) )
            return
            ;;
        *)
            # top level subcommand completion
            local subcommands="monitor \
                               resources \
                               places \
                               who \
                               show \
                               create \
                               delete \
                               add-alias \
                               del-alias \
                               set-comment \
                               set-tags \
                               add-match \
                               del-match \
                               add-named-match \
                               acquire \
                               lock \
                               release \
                               unlock \
                               release-from \
                               allow \
                               env \
                               power \
                               io \
                               console \
                               dfu \
                               fastboot \
                               flashscript \
                               bootstrap \
                               sd-mux \
                               usb-mux \
                               ssh \
                               scp \
                               rsync \
                               sshfs \
                               forward \
                               telnet \
                               video \
                               audio \
                               tmc \
                               write-image \
                               write-files \
                               reserve \
                               cancel-reservation \
                               wait \
                               reservations \
                               version \
                               export"
            COMPREPLY=( $(compgen -W "$subcommands" -- "$cur") )
            return
            ;;
        esac
    fi

    # top level subcommand found, try to complete using _labgrid_client_subcommand
    # otherwise use _labgrid_client_generic_subcommand
    local completion_func="_labgrid_client_${arg//-/_}"
    declare -f "$completion_func" >/dev/null && $completion_func || _labgrid_client_generic_subcommand
} &&
complete -F _labgrid_client labgrid-client
