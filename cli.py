from helper import *
import configparser
import typer
import glob
import re
import os

app = typer.Typer()


@app.command()
def init():
    """Cloudphoto program initialization"""
    aws_access_key_id = input("aws_access_key_id: ")
    aws_secret_access_key = input("aws_secret_access_key: ")
    bucket = input("bucket: ")
    
    if not aws_access_key_id or not aws_secret_access_key or not bucket:
        process_error('Required parameters are not defined')

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH)
    config.set(CONFIG_DEFAULT_SECTION, AWS_ACCESS_KEY_ID_PARAM_NAME, aws_access_key_id)
    config.set(CONFIG_DEFAULT_SECTION, AWS_SECRET_ACCESS_KEY_PARAM_NAME, aws_secret_access_key)
    config.set(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME, bucket)

    try:
        with open(CONFIG_FILE_PATH, 'w') as configfile:
            config.write(configfile)
    except FileNotFoundError:
        process_error(f'Config file {CONFIG_FILE_PATH} not found')

    s3 = create_s3_client(config)

    try:
        response = s3.list_buckets()
        if bucket not in [obj['Name'] for obj in response['Buckets']]:
            s3.create_bucket(Bucket=bucket)
    except Exception as e:
        process_error(f"Can not create bucket: {e}")

    process_success()


@app.command()
def upload(
    album: str = typer.Option(..., "--album", min=1, max=100),
    path: str = typer.Option(os.getcwd(), "--path", min=1, max=100),
):
    """Upload photos to cloud storage"""
    config = check_and_get_config_file()
    bucket = config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME)
    s3 = create_s3_client(config)
    check_album_name(album)
    check_dir_access(path, os.R_OK)
    
    if not os.path.exists(path):
        process_error(f'Directory {path} does not exist')

    photos = []
    for suffix in PHOTO_SUFFIXES:
        photos.extend(glob.glob(os.path.join(path, suffix)))

    if len(photos) == 0:
        process_error(f'Photos do not exist in directory = {path}')

    response = s3.list_objects(Bucket=bucket, Prefix=album+YS_SLASH)

    if 'Contents' not in response:
        s3.put_object(Bucket=bucket, Key=album + YS_SLASH)

    for photo in photos:
        try:
            with open(photo, 'rb') as data:
                s3.upload_fileobj(data, bucket, album + YS_SLASH + os.path.basename(photo))
        except Exception as e:
            print(f'An error was occured: {e}')

    process_success()


@app.command()
def download(
    album: str = typer.Option(..., "--album", min=1, max=100),
    path: str = typer.Option(os.getcwd(), "--path", min=1, max=100),
):
    """Download photos from cloud storage"""
    config = check_and_get_config_file()
    bucket = config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME)
    s3 = create_s3_client(config)
    
    response = s3.list_objects(Bucket=bucket, Prefix=album+YS_SLASH)

    if 'Contents' not in response:
        process_error(f'Album {album} does not exist')

    if not os.path.exists(path):
        os.makedirs(path)
    check_dir_access(path, os.W_OK)

    for obj in response['Contents']:
        object_name = obj['Key']
        match = re.match(PHOTO_FILE_REGEX, object_name)
        if not match:
            continue

        file_path = os.path.join(path, match.group(1))

        try:
            s3.download_file(bucket, object_name, file_path)
        except Exception as e:
            process_error(f'Error when download file: {e}')

    process_success()


@app.command()
def list(
    album: str = typer.Option(None, "--album", min=1, max=100),
):
    """View a list of albums and photos"""
    config = check_and_get_config_file()
    s3 = create_s3_client(config)

    result = []
    if album is None:
        response = s3.list_objects(Bucket=config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME))
        regex = re.compile(S3_ALBUM_REGEX)
    else:
        response = s3.list_objects(Bucket=config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME), Prefix=album+YS_SLASH)
        regex = re.compile(ALBUM_FILE_REGEX.format(album))
    
    if 'Contents' not in response:
        process_error('Album does not exist')

    for obj in response['Contents']:
        match = regex.match(obj['Key'])
        if match is not None:
            result.append(match.group(1))

    if len(result) == 0:
        process_error('Object is empty')

    process_success('\n'.join(result))


@app.command()
def delete(
    album: str = typer.Option(..., "--album", min=1, max=100),
    photo: str = typer.Option(None, "--photo", min=1, max=100),
):
    """Delete photos or albums"""
    config = check_and_get_config_file()
    s3 = create_s3_client(config)

    response = s3.list_objects(Bucket=config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME), Prefix=album+YS_SLASH)
    
    if 'Contents' not in response:
        process_error('Album does not exist')

    if photo is None:
        objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
        s3.delete_objects(
            Bucket=config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME), 
            Delete={'Objects': objects_to_delete}
        )
    else:
        key = album + YS_SLASH + photo
        if key not in [obj['Key'] for obj in response['Contents']]:
            process_error('Photo does not exist')

        s3.delete_object(
            Bucket=config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME), 
            Key=key
        )

    process_success()


@app.command('mksite')
def make_site():
    """Create and publish photo archive web page"""
    config = check_and_get_config_file()
    bucket = config.get(CONFIG_DEFAULT_SECTION, BUCKET_PARAM_NAME)
    s3 = create_s3_client(config)

    s3.put_bucket_acl(
        Bucket=bucket, 
        ACL='public-read'
    )
    s3.put_bucket_website(
        Bucket=bucket,
        WebsiteConfiguration={
            'ErrorDocument': {'Key': 'error.html'},
            'IndexDocument': {'Suffix': 'index.html'},
        }
    )

    response = s3.list_objects(Bucket=bucket)

    publish_html(ERROR_HTML_PATH, 'error.html', s3, bucket)

    if 'Contents' not in response:
        publish_html(INDEX_HTML_PATH, 'index.html', s3, bucket)
    else:
        albums_params, albums_content = prepare_albums_content(response)

        index_template = env.get_template(INDEX_HTML_PATH)
        s3.put_object(Bucket=bucket, Key='index.html', Body=index_template.render(albums=albums_params))

        for content in albums_content:
            album_template = env.get_template(ALBUM_HTML_PATH)
            s3_key, photos_content = prepare_photos_content(content, config, bucket)
            s3.put_object(Bucket=bucket, Key=s3_key, Body=album_template.render(photos=photos_content))

    process_success(WEB_SITE_URL.format(bucket))
