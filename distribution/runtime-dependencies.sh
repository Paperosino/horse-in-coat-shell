# Build-time ELF dependency closure; caller supplies qs_bin and lib_dir.
# Shared glibc/toolchain libraries are always taken from the system.
toolchain_re='^(ld-linux|libc\.so|libm\.so|libpthread|librt|libdl|libresolv|libstdc\+\+\.so|libgcc_s\.so|libatomic\.so)'

is_excluded() {
    [[ $1 =~ $toolchain_re ]]
}

have_lib() {
    [[ -e $lib_dir/$1 ]]
}

copy_lib() {
    local needed=$1 resolved=$2 real base
    real=$(readlink -f "$resolved")
    base=$(basename "$real")
    if [[ ! -e $lib_dir/$base ]]; then
        cp -a "$real" "$lib_dir/$base" || return 2
        printf 'bundled lib: %s\n' "$base"
    fi
    if [[ $needed != "$base" && ! -e $lib_dir/$needed ]]; then
        ln -sf "$base" "$lib_dir/$needed" || return 2
    fi
}

# Returns 0 when dependencies were added, 1 when unchanged, 2 on failure.
scan_deps() {
    local target=$1 copied=0 line needed resolved
    while IFS= read -r line; do
        if [[ $line =~ ^[[:space:]]*([^[:space:]]+)[[:space:]]+\=\>[[:space:]]+(/.*[^[:space:]])[[:space:]]+\(0x[[:xdigit:]]+\) ]]; then
            needed=${BASH_REMATCH[1]}
            resolved=${BASH_REMATCH[2]}
        elif [[ $line =~ ^[[:space:]]*(/.*[^[:space:]])[[:space:]]+\(0x[[:xdigit:]]+\) ]]; then
            resolved=${BASH_REMATCH[1]}
            needed=$resolved
        elif [[ $line =~ ^[[:space:]]*([^[:space:]]+)[[:space:]]+\=\>[[:space:]]+not[[:space:]]+found ]]; then
            printf 'error: missing dependency %s required by %s\n' "${BASH_REMATCH[1]}" "$target" >&2
            return 2
        else
            continue
        fi
        # NEEDED may itself be a path (e.g. /lib64/ld-linux-x86-64.so.2 on
        # glibc 2.44 ldd output); only the plain soname is ever bundled.
        needed=${needed##*/}
        [[ -e $resolved ]] || continue
        is_excluded "$needed" && continue
        have_lib "$needed" && continue
        copy_lib "$needed" "$resolved" || return 2
        copied=1
    done < <(LC_ALL=C ldd "$target" 2>/dev/null || true)
    return "$((1 - copied))"
}

# One pass over every library already in the bundle plus the qs binary.
closure_pass() {
    local copied=0 obj status
    if scan_deps "$qs_bin"; then copied=1; else
        status=$?; [[ $status == 1 ]] || return "$status"
    fi
    while IFS= read -r -d '' obj; do
        if scan_deps "$obj"; then copied=1; else
            status=$?; [[ $status == 1 ]] || return "$status"
        fi
    done < <(find "$lib_dir" -xtype f \( -name '*.so' -o -name '*.so.*' \) -print0)
    return "$((1 - copied))"
}

fixpoint() {
    local pass=0 status
    while true; do
        if closure_pass; then
            pass=$((pass + 1))
            if ((pass > 100)); then
                printf 'error: library closure did not converge\n' >&2
                return 2
            fi
        else
            status=$?
            [[ $status == 1 ]] && return 0
            return "$status"
        fi
    done
}
