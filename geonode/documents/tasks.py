#########################################################################
#
# Copyright (C) 2017 OSGeo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################
import io

from PIL import Image

from celery.utils.log import get_task_logger

from geonode.celery_app import app
from geonode.storage.manager import storage_manager

from ..base.models import ResourceBase
from .models import Document

logger = get_task_logger(__name__)


@app.task(
    bind=True,
    name='geonode.documents.tasks.create_document_thumbnail',
    queue='geonode',
    expires=600,
    time_limit=600,
    acks_late=False,
    autoretry_for=(Exception, ),
    retry_kwargs={'max_retries': 5},
    retry_backoff=3,
    retry_backoff_max=30,
    retry_jitter=False)
def create_document_thumbnail(self, object_id):
    """
    Create thumbnail for a document.
    """
    logger.debug(f"Generating thumbnail for document #{object_id}.")

    try:
        document = Document.objects.get(id=object_id)
    except Document.DoesNotExist:
        logger.error(f"Document #{object_id} does not exist.")
        raise

    image_file = None
    thumbnail_content = None

    if document.is_image:
        dname = storage_manager.path(document.files[0])
        if storage_manager.exists(dname):
            image_file = storage_manager.open(dname, 'rb')

        try:
            image = Image.open(image_file)
            with io.BytesIO() as output:
                image.save(output, format='PNG')
                thumbnail_content = output.getvalue()
                output.close()
        except Exception as e:
            logger.debug(f"Could not generate thumbnail: {e}")
        finally:
            if image_file is not None:
                image_file.close()

    if not thumbnail_content:
        logger.warning(f"Thumbnail for document #{object_id} empty.")
        ResourceBase.objects.filter(id=document.id).update(thumbnail_url=None)
    else:
        filename = f'document-{document.uuid}-thumb.jpg'
        document.save_thumbnail(filename, thumbnail_content)
        logger.debug(f"Thumbnail for document #{object_id} created.")


@app.task(
    bind=True,
    name='geonode.documents.tasks.delete_orphaned_document_files',
    queue='cleanup',
    expires=600,
    time_limit=600,
    acks_late=False,
    autoretry_for=(Exception, ),
    retry_kwargs={'max_retries': 5},
    retry_backoff=3,
    retry_backoff_max=30,
    retry_jitter=False)
def delete_orphaned_document_files(self):
    from geonode.documents.utils import delete_orphaned_document_files
    delete_orphaned_document_files()


@app.task(
    bind=True,
    name='geonode.documents.tasks.delete_orphaned_thumbnails',
    queue='cleanup',
    expires=600,
    time_limit=600,
    acks_late=False,
    autoretry_for=(Exception, ),
    retry_kwargs={'max_retries': 5},
    retry_backoff=3,
    retry_backoff_max=30,
    retry_jitter=False)
def delete_orphaned_thumbnails(self):
    from geonode.base.utils import delete_orphaned_thumbs
    delete_orphaned_thumbs()
