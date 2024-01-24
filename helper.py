
from colorama import Fore, Style
from pathlib import Path
import configparser
import jinja2
import boto3
import sys
import os
import re

# Config constants
CONFIG_FILE_PATH = str(Path.home() / ".config/cloudphoto/cloudphotorc")
CONFIG_DEFAULT_SECTION = "DEFAULT"
AWS_ACCESS_KEY_ID_PARAM_NAME = "aws_access_key_id"
AWS_SECRET_ACCESS_KEY_PARAM_NAME = "aws_secret_access_key"
BUCKET_PARAM_NAME = "bucket"
REGION_PARAM_NAME = "region"
AWS_ENDPOINT_PARAM_NAME = "endpoint_url"
DEFAULT_BUCKET_VALUE = "INPUT_BUCKET_NAME "
DEFAULT_AWS_ACCESS_KEY_ID = "INPUT_AWS_ACCESS_KEY_ID" 
DEFAULT_AWS_SECRET_ACCESS_KEY = "INPUT_AWS_SECRET_ACCESS_KEY"

# Web site
WEB_SITE_URL = 'http://{}.website.yandexcloud.net/'
ALBUM_HTML_PATH = 'cloudphoto/html/album.html'
INDEX_HTML_PATH = 'cloudphoto/html/index.html'
ERROR_HTML_PATH = 'cloudphoto/html/error.html'

# Regex
ALBUM_FILE_REGEX = '^{}\/([^\/]+)$'
S3_ALBUM_REGEX = '^([^\/]+)\/$'
ALBUM_NAME_REGEX = r'^[^\/]+$'
PHOTO_FILE_REGEX = r'^[^\/]+\/([^\/]+\.(jpg|jpeg))$'

# Files
YS_SLASH = '/'
PHOTO_SUFFIXES = ['*.jpg', '*.jpeg']

env = jinja2.Environment(loader=jinja2.FileSystemLoader('.'))


def process_error(message):
    sys.stderr.write(Fore.RED + "\n" + message + "\n" + Style.RESET_ALL)
    sys.exit(1)


def process_success():
    print(Fore.GREEN + "\nSuccessful command execution" + Style.RESET_ALL)
    sys.exit(0)


def process_success(result=None):
    if result is None:
        print(Fore.GREEN + "\nSuccessful command execution" + Style.RESET_ALL)
    else:
        print(result)
    sys.exit(0)


def create_s3_client(config):
    return boto3.client(
        aws_access_key_id=config.get(CONFIG_DEFAULT_SECTION, AWS_ACCESS_KEY_ID_PARAM_NAME),
        aws_secret_access_key=config.get(CONFIG_DEFAULT_SECTION, AWS_SECRET_ACCESS_KEY_PARAM_NAME),
        service_name='s3',
        endpoint_url=config.get(CONFIG_DEFAULT_SECTION, AWS_ENDPOINT_PARAM_NAME),
        region_name=config.get(CONFIG_DEFAULT_SECTION, REGION_PARAM_NAME)
    )


def is_config_param_invalid(param, default_value=None):
    if default_value is None:
        return len(param) == 0
    else:
        return len(param) == 0 or param == default_value


def check_and_get_config_file():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)

    try:
        aws_access_key_id = config.get(CONFIG_DEFAULT_SECTION, AWS_ACCESS_KEY_ID_PARAM_NAME)
        aws_secret_access_key = config.get(CONFIG_DEFAULT_SECTION, AWS_SECRET_ACCESS_KEY_PARAM_NAME)
        bucket = config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME)
        endpoint_url=config.get(CONFIG_DEFAULT_SECTION, AWS_ENDPOINT_PARAM_NAME)
        region_name=config.get(CONFIG_DEFAULT_SECTION, REGION_PARAM_NAME)

        if (is_config_param_invalid(aws_access_key_id, DEFAULT_AWS_ACCESS_KEY_ID) 
                or is_config_param_invalid(aws_secret_access_key, DEFAULT_AWS_SECRET_ACCESS_KEY) 
                or is_config_param_invalid(bucket, DEFAULT_BUCKET_VALUE) 
                or is_config_param_invalid(endpoint_url) 
                or is_config_param_invalid(region_name)):
            process_error('Not all params in config file are filled in')

        return config
    except Exception:
        process_error('Invalid config file')


def check_dir_access(dir_path, access_level):
    if not os.access(dir_path, access_level):
        process_error(f'Directory {dir_path} not available')


def check_album_name(album_name):
    if not re.match(ALBUM_NAME_REGEX, album_name):
        process_error(f'Invalid album name {album_name}')


def publish_html(html_path, file_name, s3, bucket):
    template = env.get_template(html_path)
    s3.put_object(Bucket=bucket, Key=file_name, Body=template.render())


def prepare_albums_content(response):
    objects = [obj['Key'] for obj in response['Contents']]
    albums = [obj.replace('/', '') for obj in objects if re.match(S3_ALBUM_REGEX, obj)]
    albums_params = [{'id': idx+1, 'name': alb} for idx, alb in enumerate(albums)]
    albums_content = []
    for alb in albums_params:
        regex = re.compile(ALBUM_FILE_REGEX.format(alb['name']))
        album_photos = []
        for obj in objects:
            if regex.match(obj):
                album_photos.append(obj)

        albums_content.append({
            'album': alb['id'],
            'photos': album_photos
        })

    return albums_params, albums_content


def prepare_photos_content(content, config, bucket):
    album_id = content['album']
    s3_key = f'album{album_id}.html'
    photos_content = []
    for photo in content['photos']:
        origin_photo_name = re.match(PHOTO_FILE_REGEX, photo).group(1)
        url = f'{config.get(CONFIG_DEFAULT_SECTION, AWS_ENDPOINT_PARAM_NAME)}/{bucket}/{photo}'
        photos_content.append({
            'url': url,
            'name': origin_photo_name
        })
        
    return s3_key, photos_content
