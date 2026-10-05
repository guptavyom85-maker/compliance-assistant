"""Application startup hooks."""
import logging
import os
import sys

from django.apps import AppConfig
from django.conf import settings


logger = logging.getLogger(__name__)


class QaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'qa'

    def ready(self):
        """Warm the embedding model once in the serving runserver process.

        SentenceTransformers/Transformers import time can be tens of seconds on
        Windows. Paying that cost before the development server accepts HTTP
        requests prevents the first question from appearing to hang. Management
        commands and the autoreloader's parent process stay lightweight.
        """
        if len(sys.argv) < 2 or sys.argv[1] != 'runserver':
            return
        autoreload_child = os.environ.get('RUN_MAIN') == 'true'
        if settings.DEBUG and '--noreload' not in sys.argv and not autoreload_child:
            return
        from rag.embedder import get_embedder
        logger.info('Loading the local embedding model before accepting questions...')
        get_embedder()
        logger.info('Local embedding model ready.')
