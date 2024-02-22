from sys import version_info
from importlib import metadata
from os import environ
from collections import OrderedDict

from django import forms
from django.urls import path
from django.shortcuts import HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from ansible_runner.interface import get_ansible_config

from aw.utils.http import ui_endpoint_wrapper
from aw.utils.subps import process
from aw.config.form_metadata import FORM_LABEL, FORM_HELP
from aw.config.main import config
from aw.config.environment import AW_ENV_VARS, AW_ENV_VARS_SECRET
from aw.model.system import SystemConfig
from aw.utils.deployment import deployment_docker


def _parsed_ansible_collections() -> dict:
    result = process(['ansible-galaxy', 'collection', 'list'])
    if result['rc'] != 0:
        return {}

    collections = {}
    col_counter = {}
    collection_path = ''
    for line in result['stdout'].split('\n'):
        if line.startswith('#'):
            collection_path = line[1:]
            continue

        if line.find('.') == -1:
            continue

        name, version = line.split(' ', 1)
        name, version = name.strip(), version.strip()
        url = f"https://galaxy.ansible.com/ui/repo/published/{name.replace('.', '/')}"

        if name in collections:
            if name in col_counter:
                col_counter[name] += 1
            else:
                col_counter[name] = 2

            name = f'{name} ({col_counter[name]})'

        collections[name] = {'version': version, 'path': collection_path, 'url': url}

    return dict(sorted(collections.items()))


def _parsed_ansible_config() -> dict:
    environ['ANSIBLE_FORCE_COLOR'] = '0'
    ansible_config_raw = get_ansible_config(action='dump', quiet=True)[0].split('\n')
    environ['ANSIBLE_FORCE_COLOR'] = '1'
    ansible_config = {}

    for line in ansible_config_raw:
        try:
            setting_comment, value = line.split('=', 1)

        except ValueError:
            continue

        setting_comment, value = setting_comment.strip(), value.strip()
        try:
            setting, comment = setting_comment.rsplit('(', 1)
            comment = comment.replace(')', '')

        except ValueError:
            setting, comment = setting_comment, '-'

        url = ("https://docs.ansible.com/ansible/latest/reference_appendices/config.html#"
               f"{setting.lower().replace('_', '-')}")

        ansible_config[setting] = {'value': value, 'comment': comment, 'url': url}

    return dict(sorted(ansible_config.items()))


def _parsed_ansible_version(python_modules) -> dict:
    versions = {'ansible': None, 'jinja': None, 'libyaml': None, 'ansible_runner': None}
    try:
        ansible_version = process(['ansible', '--version'])['stdout'].split('\n')
        versions['ansible_core'] = ansible_version[0].strip()
        versions['jinja'] = ansible_version[-2].split('=')[1].strip()
        versions['libyaml'] = ansible_version[-1].split('=')[1].strip()

        if 'ansible-runner' in python_modules:
            versions['ansible_runner'] = python_modules['ansible-runner']['version']

        if 'ansible' in python_modules:
            versions['ansible'] = python_modules['ansible']['version']

    except IndexError:
        pass

    return versions


def _parsed_python_modules() -> dict:
    modules = OrderedDict()
    try:
        module_list = [m[0] for m in metadata.packages_distributions().values()]

        for module in sorted(module_list):
            modules[module.lower()] = {'name': module, 'version': metadata.distribution(module).version}

    except (ImportError, AttributeError):
        result = process(['pip', 'list'])
        if result['rc'] != 0:
            return {}

        for line in result['stdout'].split('\n'):
            if line.find('.') == -1:
                continue

            name, version = line.split(' ', 1)
            name = name.strip()
            modules[name.lower()] = {'name': name, 'version': version.strip()}

    return modules


def get_system_versions(python_modules: dict = None, ansible_version: dict = None) -> dict:
    if python_modules is None:
        python_modules = _parsed_python_modules()

    if ansible_version is None:
        ansible_version = _parsed_ansible_version(python_modules)

    linux_versions = process(['uname', '-a'])['stdout']
    if deployment_docker():
        linux_versions += ' (dockerized)'

    return {
        'env_linux': linux_versions,
        'env_git': process(['git', '--version'])['stdout'],
        'env_ansible_core': ansible_version['ansible_core'],
        'env_ansible_runner': ansible_version['ansible_runner'],
        'env_django': python_modules['django']['version'],
        'env_django_api': python_modules['djangorestframework']['version'],
        'env_gunicorn': python_modules['gunicorn']['version'],
        'env_jinja': ansible_version['jinja'],
        'env_libyaml': ansible_version['libyaml'],
        'env_python': f"{version_info.major}.{version_info.minor}.{version_info.micro}",
    }


@login_required
@ui_endpoint_wrapper
def system_environment(request) -> HttpResponse:
    # todo: allow to check for updates (pypi, ansible-galaxy & github api)
    python_modules = _parsed_python_modules()
    ansible_version = _parsed_ansible_version(python_modules)
    env_system = get_system_versions(python_modules=python_modules, ansible_version=ansible_version)

    return render(
        request, status=200, template_name='system/environment.html',
        context={
            **env_system,
            'env_system': env_system,
            'env_python_modules': python_modules,
            'env_ansible_config': _parsed_ansible_config(),
            # 'env_ansible_roles': get_role_list(),
            'env_ansible_collections': _parsed_ansible_collections(),
        },
    )


class SystemConfigForm(forms.ModelForm):
    class Meta:
        model = SystemConfig
        fields = SystemConfig.form_fields
        field_order = SystemConfig.form_fields
        labels = FORM_LABEL['system']['config']
        help_texts = FORM_HELP['system']['config']


@login_required
@ui_endpoint_wrapper
def system_config(request) -> HttpResponse:
    config_form = SystemConfigForm()
    form_method = 'put'
    form_api = 'config'

    config_form_html = config_form.render(
        template_name='forms/snippet.html',
        context={'form': config_form, 'existing': {
            key: config[key] for key in SystemConfig.form_fields
        }},
    )
    return render(
        request, status=200, template_name='system/config.html',
        context={
            'form': config_form_html, 'form_api': form_api, 'form_method': form_method,
            'env_vars': AW_ENV_VARS, 'env_labels': FORM_LABEL['system']['config'],
            'env_vars_secret': AW_ENV_VARS_SECRET,
            'env_vars_config': {key: config[key] for key in AW_ENV_VARS},
        }
    )


urlpatterns_system = [
    path('ui/system/environment', system_environment),
    path('ui/system/config', system_config),
]
