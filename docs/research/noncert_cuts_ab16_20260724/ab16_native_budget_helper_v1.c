#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <linux/landlock.h>
#include <linux/memfd.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/prctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/sysmacros.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef F_SEAL_FUTURE_WRITE
#define F_SEAL_FUTURE_WRITE 0x0010
#endif

#define AB16_FINAL_SEALS \
    (F_SEAL_WRITE | F_SEAL_FUTURE_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL)

static int compare_ints(const void *left, const void *right) {
    const int a = *(const int *)left;
    const int b = *(const int *)right;
    return (a > b) - (a < b);
}

int ab16_memfd_create(const char *name) {
#if defined(SYS_memfd_create)
    if (name == NULL || name[0] == '\0') {
        errno = EINVAL;
        return -1;
    }
    return (int)syscall(SYS_memfd_create, name, MFD_CLOEXEC | MFD_ALLOW_SEALING);
#else
    (void)name;
    errno = ENOSYS;
    return -1;
#endif
}

int ab16_expected_final_seals(void) {
    return AB16_FINAL_SEALS;
}

int ab16_get_seals(int descriptor) {
    return fcntl(descriptor, F_GET_SEALS);
}

int ab16_install_final_seals(int descriptor) {
    if (fcntl(descriptor, F_ADD_SEALS, AB16_FINAL_SEALS) < 0) {
        return -1;
    }
    const int observed = fcntl(descriptor, F_GET_SEALS);
    if (observed < 0) {
        return -1;
    }
    if ((observed & AB16_FINAL_SEALS) != AB16_FINAL_SEALS) {
        errno = EPERM;
        return -1;
    }
    return observed;
}

int ab16_send_fd(int socket_fd, int descriptor) {
    char payload = 'F';
    struct iovec iov = {
        .iov_base = &payload,
        .iov_len = sizeof(payload),
    };
    union {
        struct cmsghdr header;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } control;
    memset(&control, 0, sizeof(control));
    struct msghdr message = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control.bytes,
        .msg_controllen = sizeof(control.bytes),
    };
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    if (header == NULL) {
        errno = EINVAL;
        return -1;
    }
    header->cmsg_level = SOL_SOCKET;
    header->cmsg_type = SCM_RIGHTS;
    header->cmsg_len = CMSG_LEN(sizeof(int));
    memcpy(CMSG_DATA(header), &descriptor, sizeof(descriptor));
    message.msg_controllen = CMSG_SPACE(sizeof(int));
    const ssize_t sent = sendmsg(socket_fd, &message, MSG_NOSIGNAL);
    if (sent != (ssize_t)sizeof(payload)) {
        if (sent >= 0) {
            errno = EIO;
        }
        return -1;
    }
    return 0;
}

int ab16_recv_fd(int socket_fd) {
    char payload = '\0';
    struct iovec iov = {
        .iov_base = &payload,
        .iov_len = sizeof(payload),
    };
    union {
        struct cmsghdr header;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } control;
    memset(&control, 0, sizeof(control));
    struct msghdr message = {
        .msg_iov = &iov,
        .msg_iovlen = 1,
        .msg_control = control.bytes,
        .msg_controllen = sizeof(control.bytes),
    };
    const ssize_t received = recvmsg(socket_fd, &message, MSG_CMSG_CLOEXEC);
    if (received != (ssize_t)sizeof(payload) || payload != 'F') {
        if (received >= 0) {
            errno = EBADMSG;
        }
        return -1;
    }
    struct cmsghdr *header = CMSG_FIRSTHDR(&message);
    if (
        header == NULL ||
        header->cmsg_level != SOL_SOCKET ||
        header->cmsg_type != SCM_RIGHTS ||
        header->cmsg_len != CMSG_LEN(sizeof(int)) ||
        CMSG_NXTHDR(&message, header) != NULL
    ) {
        errno = EBADMSG;
        return -1;
    }
    int descriptor = -1;
    memcpy(&descriptor, CMSG_DATA(header), sizeof(descriptor));
    if (descriptor < 0) {
        errno = EBADMSG;
        return -1;
    }
    return descriptor;
}

int ab16_close_range_allowlist(const int *descriptors, size_t count) {
#if defined(SYS_close_range)
    if (count > 0 && descriptors == NULL) {
        errno = EINVAL;
        return -1;
    }
    int *sorted = NULL;
    if (count > 0) {
        sorted = calloc(count, sizeof(int));
        if (sorted == NULL) {
            return -1;
        }
        memcpy(sorted, descriptors, count * sizeof(int));
        qsort(sorted, count, sizeof(int), compare_ints);
    }
    unsigned int start = 0;
    int previous = -1;
    for (size_t index = 0; index < count; ++index) {
        const int keep = sorted[index];
        if (keep < 0 || keep == previous) {
            free(sorted);
            errno = EINVAL;
            return -1;
        }
        previous = keep;
        if ((unsigned int)keep > start) {
            if (syscall(SYS_close_range, start, (unsigned int)keep - 1U, 0U) < 0) {
                free(sorted);
                return -1;
            }
        }
        if ((unsigned int)keep == UINT32_MAX) {
            start = UINT32_MAX;
            break;
        }
        start = (unsigned int)keep + 1U;
    }
    free(sorted);
    if (start != UINT32_MAX && syscall(SYS_close_range, start, UINT32_MAX, 0U) < 0) {
        return -1;
    }
    return 0;
#else
    (void)descriptors;
    (void)count;
    errno = ENOSYS;
    return -1;
#endif
}

int ab16_landlock_abi(void) {
#if defined(SYS_landlock_create_ruleset)
    return (int)syscall(
        SYS_landlock_create_ruleset,
        NULL,
        0,
        LANDLOCK_CREATE_RULESET_VERSION
    );
#else
    errno = ENOSYS;
    return -1;
#endif
}

int ab16_install_no_filesystem_writes_landlock(void) {
#if defined(SYS_landlock_create_ruleset) && defined(SYS_landlock_restrict_self)
    const uint64_t handled =
        LANDLOCK_ACCESS_FS_WRITE_FILE |
        LANDLOCK_ACCESS_FS_REMOVE_DIR |
        LANDLOCK_ACCESS_FS_REMOVE_FILE |
        LANDLOCK_ACCESS_FS_MAKE_CHAR |
        LANDLOCK_ACCESS_FS_MAKE_DIR |
        LANDLOCK_ACCESS_FS_MAKE_REG |
        LANDLOCK_ACCESS_FS_MAKE_SOCK |
        LANDLOCK_ACCESS_FS_MAKE_FIFO |
        LANDLOCK_ACCESS_FS_MAKE_BLOCK |
        LANDLOCK_ACCESS_FS_MAKE_SYM |
        LANDLOCK_ACCESS_FS_REFER |
        LANDLOCK_ACCESS_FS_TRUNCATE;
    const struct landlock_ruleset_attr attributes = {
        .handled_access_fs = handled,
    };
    const int ruleset_fd = (int)syscall(
        SYS_landlock_create_ruleset,
        &attributes,
        sizeof(attributes),
        0
    );
    if (ruleset_fd < 0) {
        return -1;
    }
    if (prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) < 0) {
        const int saved = errno;
        close(ruleset_fd);
        errno = saved;
        return -1;
    }
    if (syscall(SYS_landlock_restrict_self, ruleset_fd, 0) < 0) {
        const int saved = errno;
        close(ruleset_fd);
        errno = saved;
        return -1;
    }
    if (close(ruleset_fd) < 0) {
        return -1;
    }
    return 0;
#else
    errno = ENOSYS;
    return -1;
#endif
}

int ab16_fd_has_writable_mapping(int descriptor) {
    struct stat target;
    if (fstat(descriptor, &target) < 0) {
        return -1;
    }
    FILE *maps = fopen("/proc/self/maps", "re");
    if (maps == NULL) {
        return -1;
    }
    char *line = NULL;
    size_t capacity = 0;
    int result = 0;
    while (getline(&line, &capacity, maps) >= 0) {
        unsigned long start_address = 0;
        unsigned long end_address = 0;
        unsigned long offset = 0;
        unsigned int major_number = 0;
        unsigned int minor_number = 0;
        unsigned long inode = 0;
        char permissions[5] = {0};
        if (
            sscanf(
                line,
                "%lx-%lx %4s %lx %x:%x %lu",
                &start_address,
                &end_address,
                permissions,
                &offset,
                &major_number,
                &minor_number,
                &inode
            ) == 7 &&
            inode == (unsigned long)target.st_ino &&
            major_number == (unsigned int)major(target.st_dev) &&
            minor_number == (unsigned int)minor(target.st_dev) &&
            permissions[1] == 'w'
        ) {
            result = 1;
            break;
        }
    }
    const int saved = errno;
    free(line);
    if (fclose(maps) < 0 && result == 0) {
        return -1;
    }
    errno = saved;
    return result;
}
