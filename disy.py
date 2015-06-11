# coding=utf-8
import logging
import config
import sync

log = logging.getLogger(__name__)


if __name__ == '__main__':
    config.read()
    config.setup_logging()
    sync.Synchronizer(config.source_dict(),
                      config.dest_dict()).run()
