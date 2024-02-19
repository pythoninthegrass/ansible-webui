from os import listdir
from pathlib import Path
from functools import cache

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter

from aw.config.main import config
from aw.api_endpoints.base import API_PERMISSION, BaseResponse, GenericResponse
from aw.model.repository import Repository
from aw.execute.repository import get_path_repo_wo_isolate
from aw.utils.util import is_set


class FileSystemReadResponse(BaseResponse):
    files = serializers.ListSerializer(child=serializers.CharField())
    directories = serializers.ListSerializer(child=serializers.CharField())


class APIFsBrowse(APIView):
    http_method_names = ['get']
    serializer_class = FileSystemReadResponse
    permission_classes = API_PERMISSION

    @staticmethod
    @cache
    def _listdir(path: str) -> list[str]:
        return listdir(path)

    @classmethod
    @extend_schema(
        request=None,
        responses={
            200: FileSystemReadResponse,
            400: OpenApiResponse(GenericResponse, description='Invalid browse-selector provided'),
            403: OpenApiResponse(GenericResponse, description='Traversal not allowed'),
            404: OpenApiResponse(GenericResponse, description='Base directory does not exist'),
        },
        summary='Return list of existing files and directories.',
        description="This endpoint is mainly used for form auto-completion when selecting job-files",
        parameters=[
            OpenApiParameter(
                name='repository', type=int, default=None, required=False,
                description='Repository to query',
            ),
            OpenApiParameter(
                name='base', type=str, default='/', description='Relative directory to query',
                required=False,
            ),
        ],
    )
    def get(cls, request, repository: int = None):
        browse_root = Path(config['path_play'])
        items = {'files': [], 'directories': []}

        if repository not in [None, 0, '0']:
            try:
                repository = Repository.objects.get(id=repository)
                if repository is None:
                    raise ObjectDoesNotExist

                if repository.rtype_name == 'Static':
                    browse_root = repository.static_path

                else:
                    if repository.git_isolate:
                        # do not validate as the repo does not exist..
                        all_valid = ['.*']
                        items['files'] = all_valid
                        items['directories'] = all_valid
                        return Response(items)

                    browse_root = get_path_repo_wo_isolate(repository)
                    if is_set(repository.git_playbook_base):
                        browse_root = browse_root / repository.git_playbook_base

            except ObjectDoesNotExist:
                return Response(data={'msg': 'Provided repository does not exist'}, status=404)

        if not browse_root.is_dir():
            return Response(data={'msg': 'Base directory does not exist'}, status=404)

        if 'base' not in request.GET:
            base = '/'
        else:
            base = str(request.GET['base'])

        if base.find('..') != -1:
            return Response(data={'msg': 'Traversal not allowed'}, status=403)

        raw_items = cls._listdir(browse_root / base)

        for item in raw_items:
            item_path = browse_root / base / item
            if item_path.is_file():
                items['files'].append(item)
            elif item_path.is_dir():
                items['directories'].append(item)

        return Response(items)
