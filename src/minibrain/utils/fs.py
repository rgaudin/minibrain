import stat


def perms_to_mode(perms: str) -> int:
    """Unix file mode from human-readable string"""
    mode = 0

    ftype_mode = {
        "l": stat.S_IFLNK,
        "s": stat.S_IFSOCK,
        "-": stat.S_IFREG,
        "b": stat.S_IFBLK,
        "d": stat.S_IFDIR,
        "c": stat.S_IFCHR,
        "p": stat.S_IFIFO,
    }.get(perms[0])
    if ftype_mode:
        mode |= ftype_mode

    # owner
    for index, perm in enumerate(("r", "w", "x")):
        if perms[1 + index] == perm:
            mode |= getattr(stat, f"S_I{perm.upper()}USR")
    # setuid
    if perms[3] == "s":
        mode |= stat.S_ISUID
    # setuid AND +x
    elif perms[3] == "S":
        mode |= stat.S_ISUID | stat.S_IXUSR

    # group
    for index, perm in enumerate(("r", "w", "x")):
        if perms[4 + index] == perm:
            mode |= getattr(stat, f"S_I{perm.upper()}GRP")

    # setgid
    if perms[6] == "S":
        mode |= stat.S_ISGID
    # setgid AND +x
    elif perms[6] == "s":
        mode |= stat.S_ISGID | stat.S_IXGRP

    # other
    for index, perm in enumerate(("r", "w", "x")):
        if perms[7 + index] == perm:
            mode |= getattr(stat, f"S_I{perm.upper()}OTH")

    # sticky bit
    if perms[9] == "T":
        mode |= stat.S_ISVTX
    # sticky bit AND +x
    elif perms[9] == "t":
        mode |= stat.S_ISVTX | stat.S_IXOTH

    return mode


def is_world_readable(mode: int) -> bool:
    """whether mode reflects a world-readable file"""
    return mode | stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH == mode


def get_normalized_path(path: str) -> str:
    # normalize a File entry path as relative path, always
    while path[0] == "/":
        path = path[1:]
    # remove double slashes
    return path.replace("//", "/")
