#!/usr/bin/env python
# -*- coding: utf-8 -*-

###############################################################################
#  Copyright 2013 Kitware Inc.
#
#  Licensed under the Apache License, Version 2.0 ( the "License" );
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################

import cherrypy
import datetime

from .model_base import Model, ValidationException
from girder.utility import assetstore_utilities


class Upload(Model):
    """
    This model stores temporary records for uploads that have been approved
    but are not yet complete, so that they can be uploaded in chunks of
    arbitrary size. The chunks must be uploaded in order.
    """
    def initialize(self):
        self.name = 'upload'
        self.assetstoreAdapter = assetstore_utilities.getAssetstoreAdapter()

    def validate(self, doc):
        if doc['size'] < 0:
            raise ValidationException('File size must not be negative.')
        if doc['received'] > doc['size']:
            raise ValidationException('Received bytes must not be larger than '
                                      'the total size of the upload.')
        return doc

    def handleChunk(self, upload, chunk):
        """
        When a chunk is uploaded, this should be called to process the chunk.
        If this is the final chunk of the upload, this method will finalize
        the upload automatically.
        :param upload: The upload document to update.
        :type upload: dict
        :param chunk: The file object representing the chunk that was uploaded.
        :type chunk: file
        """
        upload = self.save(self.assetstoreAdapter.uploadChunk(upload, chunk))

        # If upload is finished, we finalize it
        if upload['received'] == upload['size']:
            self.finalizeUpload(upload)

    def finalizeUpload(self, upload):
        """
        This should only be called manually in the case of creating an
        empty file, i.e. one that has no chunks. It simply
        """
        if upload['parentType'] == 'folder':
            # Create a new item with the name of the file.
            item = self.model('item').createItem(
                name=upload['name'], creator={'_id': upload['userId']},
                folder={'_id': upload['parentId']})
        else:
            # Uploading into an existing item
            item = {'_id': upload['parentId']}

        file = self.model('file').createFile(
            item=item, name=upload['name'], size=upload['size'],
            creator={'_id': upload['userId']})

        file = self.assetstoreAdapter.finalizeUpload(upload, file)
        self.model('file').save(file)
        self.remove(upload)

    def createUpload(self, user, name, parentType, parent, size):
        """
        Creates a new upload record, and creates its temporary file
        that the chunks will be written into. Chunks should then be sent
        in order using the _id of the upload document generated by this method.

        :param user: The user performing the upload.
        :type user: dict
        :param name: The name of the file being uploaded.
        :type name: str
        :param parentType: The type of the parent being uploaded into.
        :type parentType: str ('folder' or 'item')
        :param parent: The document representing the parent.
        :type parentId: dict
        :param size: Total size in bytes of the whole file.
        :type size: int
        :returns: The upload document that was created.
        """
        now = datetime.datetime.now()
        upload = {
            'created': now,
            'updated': now,
            'userId': user['_id'],
            'parentType': parentType.lower(),
            'parentId': parent['_id'],
            'size': size,
            'name': name,
            'received': 0
            }
        upload = self.assetstoreAdapter.initUpload(upload)
        return self.save(upload)
