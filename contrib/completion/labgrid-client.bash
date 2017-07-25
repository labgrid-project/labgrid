# complete labgrid-client
_labgrid-client()
{
    local cur=${COMP_WORDS[COMP_CWORD]}
    local prev=${COMP_WORDS[COMP_CWORD-1]}

    case "$prev" in
	-p)
	    local mine_places=('power' 'console' 'release' 'env')
	    if [[ ! -z "${mine_places[${COMP_WORDS[1]}]+_}" ]]; then
		COMPREPLY=( $( compgen -W "$(labgrid-client complete places -m)" ) )
	    else
		COMPREPLY=( $( compgen -W "$(labgrid-client complete places)" ) )
	    fi
	    return 0
	    ;;
	power)
	    COMPREPLY=( $( compgen -W "on off cycle get" ) )
	    return 0
	    ;;
    esac

    # completing an option
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $( compgen -W "-p -h -x" ) )
    else
        COMPREPLY=( $( compgen -W "resources\
                                   places\
                                   show\
				   help\
                                   add-place\
                                   del-place\
                                   add-alias\
                                   del-alias\
                                   set-comment\
                                   add-match\
                                   del-match\
                                   acquire\
                                   release\
                                   env\
                                   power\
                                   console" ) )
    fi
}
complete -F _labgrid-client labgrid-client
