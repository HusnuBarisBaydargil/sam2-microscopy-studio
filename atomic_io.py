import os
import shutil
import tempfile

BACKUP_SUFFIX = ".bak"


def backup_path(path):
    return f"{os.fspath(path)}{BACKUP_SUFFIX}"


def recoverable_file_exists(path):
    return os.path.exists(path) or os.path.exists(backup_path(path))


def read_with_backup(path, reader):
    primary_error = None
    try:
        return reader(path)
    except Exception as error:
        primary_error = error

    recovery_path = backup_path(path)
    if os.path.exists(recovery_path):
        try:
            return reader(recovery_path)
        except Exception:
            pass
    raise primary_error


def _sync_file(path):
    with open(path, "r+b") as file:
        os.fsync(file.fileno())


def _remove_if_present(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _replace_backup(source_path, recovery_path, directory):
    descriptor, temporary_backup = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(recovery_path)}.",
        suffix=".tmp",
    )
    os.close(descriptor)
    try:
        shutil.copyfile(source_path, temporary_backup)
        _sync_file(temporary_backup)
        os.replace(temporary_backup, recovery_path)
    finally:
        _remove_if_present(temporary_backup)


def atomic_write_file(path, writer, *, validator=None, keep_backup=True):
    target_path = os.path.abspath(os.fspath(path))
    directory = os.path.dirname(target_path)
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=f".{os.path.basename(target_path)}.",
        suffix=".tmp",
    )
    os.close(descriptor)

    try:
        writer(temporary_path)
        _sync_file(temporary_path)
        if validator is not None:
            validator(temporary_path)

        if keep_backup and os.path.exists(target_path):
            current_is_valid = True
            if validator is not None:
                try:
                    validator(target_path)
                except Exception:
                    current_is_valid = False
            if current_is_valid:
                _replace_backup(target_path, backup_path(target_path), directory)

        os.replace(temporary_path, target_path)
    finally:
        _remove_if_present(temporary_path)
