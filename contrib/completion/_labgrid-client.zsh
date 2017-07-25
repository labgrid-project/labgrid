#compdef labgrid-client
_labgrid-client () {
local curcontext="${curcontext}"
typeset -A opt_args
_arguments -C "1:Actions:((resources\:'show resources'\
                        places\:'show places'\
                        show\:'show current place'\
                        add-place\:'add place'\
                        del-place\:'delete place'\
                        add-alias\:'add alias for a place'\
                        del-alias\:'delete alias for a place'\
                        set-comment\:'set comment for a place'\
                        add-match\:'add match to a place'\
                        del-match\:'delete match from a place'\
                        acquire\:'acquire a place'\
                        release\:'release a place'\
                        env\:'print environment'\
                        power\:'power management'\
                        help\:'show help'\
                        console\:'open console'))" \
	                '*::arg:->args'
case "$state" in
    (args)
	case $line[1] in
	    (power)
		_arguments -C "1:Power parameter:((on\:'power device on'\
                                                   off\:'power device off'
                                                   get\:'get power status'
                                                   cycle\:'cycle the device'))" \
		              '-p[place or alias]:place:->places' \
			      '-h[show help]' \
			      '-x[crossbar url]'
		;;
	    (add-match)
		_arguments -C "1:Resource Match:->resources" \
		;;
	    (*)
		_arguments -C '-p[place or alias]:place:->places' \
			      '-h[show help]' \
		              '-x[crossbar url]'
		;;
	esac
	case "$state" in
	    (places)
		local -a places mine_places
		mine_places=('power' 'console' 'release' 'env')
		if [[ ${mine_places[(i)$line[1]]} -le ${#mine_places} ]];
		   then places=( $(labgrid-client complete -m places) )
			_values 'Available places and aliases' $places
		else
		    places=( $(labgrid-client complete places) )
		    _values 'Available places and aliases' $places
		fi
		;;
	    (resources)
		local -a resources
		resources=( $(labgrid-client complete resources) )
		_values 'Exported Resources' $resources
		;;
	esac
esac

}
