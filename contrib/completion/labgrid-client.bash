# complete labgrid-client
_labgrid-client()
{
    local cur=${COMP_WORDS[COMP_CWORD]}
    local prev=${COMP_WORDS[COMP_CWORD-1]}

    case "$prev" in
	-p)
	    COMPREPLY=( $( compgen -W "$(labgrid-client -x ws://dude.hi.4.pengutronix.de:20408/ws  complete places)" -- $cur ) )
	    return 0
	    ;;
	power)
	    COMPREPLY=( $( compgen -W "on off cycle get" -- $cur ) )
	    return 0
	    ;;
    esac

    # completing an option
    if [[ "$cur" == -* ]]; then
        COMPREPLY=( $( compgen -W "-p -h -x" -- $cur ) )
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
                                   console" -- $cur ) )
    fi
}
complete -F _labgrid-client labgrid-client
