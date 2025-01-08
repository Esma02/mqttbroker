import os
import json
from django.conf import settings

def add_database_to_config(db_name,user="postgres",password="123",host='localhost',port="5432"):
    db_config_path = os.path.join(settings.BASE_DIR,'db_config.json')
    #mevcut veritabanları
    if os.path.exists(db_config_path):
        with open(db_config_path,'r') as f:
            db_config=json.load(f)
    else:
        db_config={}
    #yeni veritabanı ekle
    db_config[db_name]={
        "ENGINE":"django.db.backends.postgresql",
        "NAME":db_name,
        "USER":user,
        "PASSWORD":password,
        "HOST":host,
        "PORT":port
    }
     
    #yeni veritabanını dosyaya yaz
    with open(db_config_path,'w') as f:
        json.dump(db_config,f,indent=4)


    #yeni ayarları yükle
    settings.DATABASES[db_name]=db_config[db_name]
