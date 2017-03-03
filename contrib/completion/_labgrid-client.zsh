#compdef labgrid-client
_labgrid-client () {
local curcontext="${curcontext}"
local -a options
local context state state_descr line
typeset -A opt_args
_arguments "1:Actions:((resources\:'show resources' places\:'show places' show\:'show current place' add-place\:'add place' del-place\:'delete place' add-alias\:'add alias for a place' del-alias\:'delete alias for a place' set-comment\:'set comment for a place' add-match\:'add match to a place' del-match\:'delete match from a place' acquire\:'acquire a place' release\:'release a place' env\:'print environment' power\:'power management' console\:'open console'))"\
  '-p[place or alias]:place:->places' '-h[show help]' '-x[crossbar url]'
case "$state" in
    places)
        local -a places
        places=( $(labgrid-client complete places) )
        _values -s , 'places' music_files
        ;;
esac

}
