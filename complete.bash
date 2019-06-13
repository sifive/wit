_wit()
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"

    global_flags="-h --help -v -vv -vvv -vvvv --verbose --version -C --repo-path --prepend-repo-path"

    if [[ ${prev} == wit ]] ; then
        if [[ ${cur} == -* ]] ; then
            COMPREPLY=( $(compgen -W "${global_flags}" -- ${cur}) )
            return 0
        else
            opts="init add-pkg update-pkg add-dep update-dep status update fetch-scala"
            COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
            return 0
        fi
    elif [[ ${prev} == -C ]] || [[ ${prev} == --repo-path ]] || [[ ${prev} == --prepend-repo-path ]] ; then
        comptopt -o filenames 2>/dev/null
        COMPREPLY=( $(compgen -f -- ${cur}) )
        return 0
    elif [[ ${prev} == init ]] ; then
        if [[ ${cur} == -* ]] ; then
            additional="--no-update --no-fetch-scala -a --add-pkg"
            COMPREPLY=( $(compgen -W "${global_flags} ${additional}" -- ${cur}) )
            return 0
        else
            comptopt -o filenames 2>/dev/null
            COMPREPLY=( $(compgen -f -- ${cur}) )
            return 0
        fi
    fi

    comptopt -o filenames 2>/dev/null
    COMPREPLY=( $(compgen -f -- ${cur}) )
    return 0
}
complete -F _wit wit

