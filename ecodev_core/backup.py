"""
Module implementing backup mechanism on a ftp server.
"""
import tarfile
from datetime import datetime
from pathlib import Path
from subprocess import PIPE
from subprocess import Popen
from subprocess import run
from subprocess import STDOUT
from typing import List

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.db_connection import DB_URL
from ecodev_core.logger import logger_get


log = logger_get(__name__)


class BackUpSettings(BaseSettings):
    """
    Settings class used to connect to the ftp server backup
    """
    backup_username: str = ''
    backup_password: str = ''
    backup_url: str = ''
    model_config = SettingsConfigDict(env_file='.env')


BCK = BackUpSettings()
BACKUP_URL = f'ftp://{BCK.backup_username}:{BCK.backup_password}@{BCK.backup_url}'


def backup(backed_folder: Path, nb_saves: int = 5, additional_id: str = 'default') -> None:
    """
    Backup db and backed_folder: write the dump/tar on the backup server and erase old copies
    """
    timestamp = datetime.now().strftime('%Y_%m_%d_%Hh_%Mmn_%Ss')
    _backup_db(Path.cwd() / f'{additional_id}_db.{timestamp}.dump', nb_saves)
    _backup_files(backed_folder, Path.cwd() / f'{additional_id}_files.{timestamp}.tgz', nb_saves)


def _backup_db(db_dump_path: Path, nb_saves: int) -> None:
    """
    Pg_dump of DB_URL db andwrite on the backup server
    """
    process = Popen(['pg_dump', f'--dbname={DB_URL}', '-f', db_dump_path.name],
                    stdout=PIPE, stderr=STDOUT, cwd=db_dump_path.parent)
    if not (process.communicate()[0]):
        _backup_content(db_dump_path, nb_saves)


def _backup_files(backed_folder: Path, backup_file: Path, nb_saves: int) -> None:
    """
    Zip backed_folder and write on the backup server
    """
    with tarfile.open(backup_file, 'w:gz') as tar:
        tar.add(backed_folder, arcname=backed_folder.name)
    _backup_content(backup_file, nb_saves)


def _backup_content(file_to_backup: Path, nb_saves: int) -> None:
    """
    Write file_to_backup on the backup server and delete versions so as to keep only nb_saves copies
    """
    log.warning(f'Transferring backup to server: {file_to_backup}')
    run(['lftp', '-c', f'open {BACKUP_URL}; put {file_to_backup}'])
    backups_to_delete = _get_old_backups(file_to_backup, nb_saves)
    log.info(f'deleting remote backups {backups_to_delete}')
    for to_rm in backups_to_delete:
        run(['lftp', '-c', f'open {BACKUP_URL}; rm {to_rm}'], capture_output=True, text=True)
    log.info(f'deleting local {file_to_backup}')
    file_to_backup.unlink()


def _get_old_backups(file_to_backup: Path, nb_saves: int) -> List[str]:
    """
    Retrieve old versions of file_to_backup in order to erase them (more than nb_saves ago)
    """
    output = run(['lftp', '-c', f'open {BACKUP_URL}; ls'],
                 capture_output=True, text=True)
    filename_base = file_to_backup.name.split('.')[0]
    all_backups = sorted([x.split(' ')[-1]
                         for x in output.stdout.splitlines() if filename_base in x])
    log.info(f'existing remote backups {all_backups}')
    return all_backups[:-nb_saves]
