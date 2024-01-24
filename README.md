## Порядок сборки приложения

1. Клонировать репозиторий в домашнюю директорию текущего пользователя

```bash
git clone https://github.com/KristinaVydrenkova/os-homework_2-cloud_photo.git
```

2. Выполнить в bash команду для установки необходимых python библиотек. 

```bash
pip3 install -r os-homework_2-cloud_photo/requirements.txt 
``` 

3. В файл ~/.bashrc добавить алиас для запуска программы 

```bash
cloudphoto() {
    python3 cloudphoto "$@"
}
``` 

4. Применить изменения командой
```bash
source .bashrc
``` 

5. В .config добавить папку cloudphoto с файлом конфигурации cloudphotorc 

6. Перед началом работы необходимо инициализировать программу, определив необходимые параметры:
   
```bash
cloudphoto init
```  
