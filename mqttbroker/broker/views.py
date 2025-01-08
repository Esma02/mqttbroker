from django.views import View
from django.http import JsonResponse
from django.shortcuts import render
from requests import options
from .models import BrokerConnection, DynamicTable
import paho.mqtt.client as mqtt
import json
import psycopg2
from threading import Thread
from datetime import datetime
from django.http import HttpResponse
from django.conf import settings
import os
from django.db import connections
from .conf import add_database_to_config

class CreateTable(View):
    def get(self, request):  #->oluşturulan tabloları görüntüleme için kullandık
        tables = DynamicTable.objects.all()
        return render(request, 'create_table.html', {'tables': tables})

    def post(self, request): #->broker bilgileri ile yeni connection,yeni tablo,topice abone,gelen mesajları veritabanına kaydı halleder
        broker_ip = request.POST.get('broker-ip', '').strip()
        port = request.POST.get('port', '').strip()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        topic = request.POST.get('topic', '').strip()
        user_column_names = request.POST.getlist('user-column-name')
        user_column_types = request.POST.getlist('user-column-type')

        if not all([broker_ip, port, username, password, topic]):
            return JsonResponse({'error': 'Geçerli bir Broker IP, port, kullanıcı adı, şifre ve topic adı girin.'}, status=400)
        #broker bağlantısının veritabanı kaydı
        broker_conn = BrokerConnection.objects.create(
            broker_ip=broker_ip,
            port=port,
            username=username,
            password=password,
            topic=topic
        )

        try:
            #veritabanı bağlantısı
            conn = psycopg2.connect(
                dbname='broker',
                user='postgres',
                password='123',
                host='localhost',
                port='5432',
                options='-c client_encoding=UTF8'

            )
            cursor = conn.cursor()

            #Veitabanı tablosu oluşturma sorgusu
            
            table_name = topic
            tn=table_name.lower()
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS {tn} (
                id BIGSERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            cursor.execute(create_table_query)
            
            #kullanıcının girdiği kolonları ekleme
            for name, col_type in zip(user_column_names, user_column_types):
                if name:
                    column_query = f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {name} {col_type};"
                    cursor.execute(column_query)
                    print(f"Kolon eklendi: {name} ({col_type})")

            conn.commit()
            DynamicTable.objects.create(table_name=table_name)
            print("Tablo ve kolonlar başarıyla oluşturuldu.")

        except Exception as e:
            print(f"Veritabanı hatası: {e}")
            return JsonResponse({'error': str(e)}, status=500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        client = mqtt.Client()
        client.username_pw_set(username, password)

        def on_message(client, userdata, msg):#gelen mesajı işleyip veritabanına kaydetme
            print(f"Messages: {msg.topic} {msg.payload.decode()}")
            try:
                raw_data = raw_data.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')  # Örnek görünmez karakterler

                json_data = json.loads(msg.payload.decode())
                values = [json_data.get(name) for name in user_column_names]

                conn = psycopg2.connect(
                    dbname='broker',
                    user='postgres',
                    password='123',
                    host='localhost',
                    port='5432',
                    options='-c client_encoding=UTF8'

                )
                cursor = conn.cursor()

                insert_query = f"""
                INSERT INTO {table_name} ({', '.join(user_column_names)})
                VALUES ({', '.join(['%s'] * len(user_column_names))});
                """
                cursor.execute(insert_query, values)
                conn.commit()
                print("Data saved successfully")
            except json.JSONDecodeError:
                print("JSON çözümleme hatası.")
            except Exception as e:
                print(f"Mesaj işleme hatası: {e}")
                print(f"Gelen veri: {json_data}")
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()

        

        client.on_connect = lambda client, userdata, flags, rc: (
            print("Broker baglanti sağlandı."),
            client.subscribe(topic)
        )
        client.on_message = on_message

        try:
            client.connect(broker_ip, int(port), 60)
            Thread(target=client.loop_forever).start()
        except Exception as e:
            print(f"MQTT baglanti hatası: {e}")
            return JsonResponse({'error': 'MQTT baglanti sağlanamadı.'}, status=500)

        return JsonResponse({'message': f'Table "{topic}" successfully created and connected to the broker.'})





class StartBrokerConnection(View):#-Mevcut olan veritabanına bağlanıp gelen verileri işleme
    def __init__(self):
        super().__init__()
        self.client = None
        self.user_column_names = []

    def get_table_columns(self, table_name):
        """Belirtilen tablodaki kolon adları"""
        try:
            conn = psycopg2.connect(
                dbname='broker',
                user='postgres',
                password='123',
                host='localhost',
                port='5432',
                options='-c client_encoding=UTF8'

            )
            cursor = conn.cursor()
            query = f"""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s;
            """
            cursor.execute(query, (table_name,))
            columns = cursor.fetchall()
            return [column[0] for column in columns]
        except Exception as e:
            print(f"Hata: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def post(self, request):  # tablo adına göre mqtt bağlantısı oluşturma
        table_name = request.POST.get('table_name')

        if not table_name:
            return JsonResponse({'error': 'Tablo adı sağlanmadı.'}, status=400)

        broker_conns = BrokerConnection.objects.filter(topic=table_name)

        if not broker_conns.exists():
            return JsonResponse({'error': 'Broker connection not found'}, status=404)

        #ilk broker kaydını al
        broker_conn = broker_conns.first()
        broker_ip = broker_conn.broker_ip
        port = broker_conn.port
        username = broker_conn.username
        password = broker_conn.password

        # Tablonun kolonlarını al
        self.user_column_names = self.get_table_columns(table_name)

        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)

        def on_connect(client, userdata, flags, rc):
            if rc == 0:  # bağlantı başarılıysa
                print("Connection is successfully.")
                client.subscribe(table_name)
            else:
                print(f"Connection error, kod: {rc}")

        def on_message(client, userdata, msg):
            print(f"Gelen mesaj: {msg.topic} - {msg.payload.decode()}")
            try:
                # Ham veriyi çözümle
                raw_data = msg.payload.decode().strip()
                
                # Görünmez karakterleri temizle
                raw_data = raw_data.replace('\u200b', '').replace('\u200c', '').replace('\u200d', '')  # Örnek görünmez karakterler
                # raw_data = raw_data.encode('ascii', 'ignore').decode('ascii')  # ASCII dışındaki karakterleri kaldır
                # #raw_data = ''.join(raw_data.splitlines())  # Satır sonlarını temizle

                
                json_data = json.loads(raw_data)
                print(f"Gelen JSON verisi: {json_data}")


            #     # Gelen veriyi kaydet
            #     save_to_database(json_data)
            # except json.JSONDecodeError as e:
            #     print(f"JSON çözümleme hatası: {e}")
            # except Exception as e:
            #     print(f"Veritabanı hatası: {e}")

                # Gelen verinin bir liste olup olmadığını kontrol et
                if isinstance(json_data, list) and len(json_data) > 0:
                    item = json_data[0]  # İlk öğeyi al
                else:
                    item = json_data  # Eğer liste değilse doğrudan kullan

                save_to_database(item)  # İlk öğeyi veritabanına kaydet
            except json.JSONDecodeError as e:
                print(f"JSON çözümleme hatası: {e}")
                print(f"Hatalı JSON verisi: {raw_data}") 
                print(f"Hatalı JSON verisi: {msg.payload.decode()}")
            except Exception as e:
                print(f"Veritabanı hatası: {e}")

        def save_to_database(json_data):
            try:
                conn = psycopg2.connect(
                    dbname='broker',
                    user='postgres',
                    password='123',
                    host='localhost',
                    port='5432',
                    options='-c client_encoding=UTF8'
                )
                cursor = conn.cursor()

                # Gelen veriden sütun adlarını ve değerleri ayıkla
                columns = []
                values = []

                for name in self.user_column_names:
                    if name in json_data:
                        value = json_data[name]
                        values.append(value if value is not None and value != "" else ' ')
                        columns.append(name)

                # Sorgu, veritabanı kayıt işlemi
                if columns:
                    insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))});"
                    
                    try:
                        cursor.execute(insert_query, values)
                        conn.commit()
                        print("Data saved successfully.")
                    except Exception as e:
                        print(f"Veri kaydetme hatası: {e}")
                else:
                    print("Veri kaydedilemedi, çünkü 'columns' listesi boş.")
            except Exception as e:
                print(f"Veritabanı bağlantı hatası: {e}")
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    conn.close()


        # MQTT bağlantı ayarları
        self.client.on_connect = on_connect
        self.client.on_message = on_message

        try:
            self.client.connect(broker_ip, port, 60)
            Thread(target=self.client.loop_forever).start()  # MQTT dinleyicisini başlat
        except Exception as e:
            print(f"MQTT bağlantı hatası: {e}")
            return JsonResponse({'error': 'MQTT bağlantı sağlanamadı.'}, status=500)

        return JsonResponse({'message': f'Broker bağlantı "{table_name}" için başlatıldı.'})


    # def stop_broker_connection(self):
    #     if self.client and self.is_connected:
    #         self.client.disconnect()
    #         self.is_connected = False  # Bağlantı durumu güncelleniyor
    #         print("Broker bağlantısı durduruldu.")






class StopBrokerConnection(View):  # bağlantıyı kesmek için
    def post(self, request):
        table_name = request.POST.get('table_name')

        start_broker_connection_instance = StartBrokerConnection()
        start_broker_connection_instance.stop_broker_connection()  # StartBrokerConnection'dan fonksiyonu çağırıyoruz

        return JsonResponse({'message': f'Broker baglanti "{table_name}" için durduruldu.'})
    




class FilterTableData(View):
    def get(self, request):
        default_columns = ['Column1', 'Column2', 'Column3']
        default_rows = [
            ['2023-01-01 10:00:00', 100, 200],
            ['2023-01-02 11:00:00', 150, 250],
            ['2023-01-03 12:00:00', 200, 300],
        ]
        return render(request, 'filtered_table.html', {
            'columns': default_columns,
            'filtered_rows': default_rows,
            'table_name': 'default_table',
            'error': None
        })

    def post(self, request):
        table_name = request.POST.get('table_name')
        selected_columns = request.POST.getlist('columns')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if not table_name or not selected_columns or not start_date or not end_date:
            error = "Tablo adı, seçilen kolonlar veya tarih aralıkları belirtilmedi."
            return render(request, 'filtered_table.html', {
                'error': error,
                'table_name': table_name,
                'filtered_rows': [],
                'columns': []
            })

        try:
            start_date = datetime.fromisoformat(start_date)
            end_date = datetime.fromisoformat(end_date)
        except ValueError:
            error = "Tarih formatı hatalı."
            return render(request, 'filtered_table.html', {
                'error': error,
                'table_name': table_name,
                'filtered_rows': [],
                'columns': []
            })

        filtered_rows = []
        columns = []

        try:
            conn = psycopg2.connect(
                dbname='broker',
                user='postgres',
                password='123',
                host='localhost',
                port='5432',
                options='-c client_encoding=UTF8'
            )
            cursor = conn.cursor()

            selected_columns_str = ", ".join(selected_columns)
            query = f"SELECT {selected_columns_str} FROM {table_name} WHERE created_at BETWEEN %s AND %s;"
            cursor.execute(query, (start_date, end_date))
            filtered_rows = cursor.fetchall()

            columns = selected_columns

            # Terminalde verileri yazdır
            print("Selected Columns:", selected_columns)
            print("Filtered Rows:", filtered_rows)
            

        except Exception as e:
            error = f"Veritabanı hatası: {str(e)}"
            return render(request, 'filtered_table.html', {
                'error': error,
                'table_name': table_name,
                'filtered_rows': [],
                'columns': []
            })
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        formatted_rows = []
        for row in filtered_rows:
            formatted_row = []
            for value in row:
                if isinstance(value, datetime):
                    formatted_value = value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-4]
                else:
                    formatted_value = value
                formatted_row.append(formatted_value)
            formatted_rows.append(formatted_row)

        return render(request, 'filtered_table.html', {
            'columns': columns,
            'filtered_rows': formatted_rows,
            'table_name': table_name,
            'filtered_rows_json': json.dumps(formatted_rows)  # JSON formatında
        })

class GetColumns(View):
    def get(self, request, table_name):
        try:
            conn = psycopg2.connect(
                dbname='broker',
                user='postgres',
                password='123',
                host='localhost',
                port='5432',
                options='-c client_encoding=UTF8'
            )
            cursor = conn.cursor()

            cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';")
            columns = [col[0] for col in cursor.fetchall()]

        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        return JsonResponse({'columns': columns})

class ShowTableData(View):
    def get(self,request): #başlangıç verileri gösterme
        return render(request,'table_data.html',{
            'rows':[],
            'columns':[],
            'table_name':None
        })




    def post(self, request):#belirtilen tablodaki verileri alır işler
        table_name = request.POST.get('table_name')
        limit = 250  

        if 'show_more' in request.POST:
            limit = 500 

        try:
            conn = psycopg2.connect(
                dbname='broker',
                user='postgres',
                password='123',
                host='localhost',
                port='5432',
                options='-c client_encoding=UTF8'

            )
            cursor = conn.cursor()
            
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT %s;", (limit,))
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]

        except Exception as e:
            print(f"Veritabanı hatası: {e}")
            return JsonResponse({'error': str(e)}, status=500)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
            
        istenentarih = []
        for row in rows:
            dönütarih = []
            for value in row:
                if isinstance(value, datetime):
                    formatted_value = value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-4] #2 basamak al
                else:
                    formatted_value = value
                dönütarih.append(formatted_value)
            istenentarih.append(dönütarih)

        return render(request, 'table_data.html', {'rows': istenentarih, 'columns': columns, 'table_name': table_name})


def index(request):
    return render(request,'index.html')


class TopcListView(View):
    def get(self,request):
        tables=DynamicTable.objects.all()

        return render(request,'topic_list.html',{
            'tables':tables,

        })



def create_database(request):
    if request.method == 'POST':
        db_name = request.POST.get('db_name')
        user = 'postgres'
        password = '123'

        # Veritabanını oluştur
        try:
            connection = psycopg2.connect(user='postgres', password='123', host='localhost', port='5432')
            connection.autocommit = True
            cursor = connection.cursor()
            cursor.execute(f"CREATE DATABASE {db_name}")
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {user}")
            cursor.close()
            connection.close()
            # Dinamik olarak DATABASES ayarını ekle
            add_database_to_config(db_name, user, password)
            return HttpResponse("Veritabanı başarıyla oluşturuldu ve ayarlar eklendi!")
        except Exception as e:
            return HttpResponse(f"Bir hata oluştu: {e}")
    return render(request, 'create_database.html')


def add_database_to_connections(db_name, user, password):
    
    add_database_to_connections(db_name,user,password)

    # Yeni veritabanını Django bağlantılarına ekleyin
    connections.databases = settings.DATABASES



def use_custom_database(request):
    if request.method == 'POST':
        db_name = request.POST.get('db_name')  # Kullanıcının oluşturduğu veritabanı adı
        if not db_name:
            return render(request,'use_database.html')
        
        # Veritabanı adını kontrol et
        if db_name not in connections.databases:
            return render(request, 'use_database.html', {
                'success': False,
                'error': f"Veritabanı '{db_name}' bulunamadı."
            })

        try:
            # Dinamik bağlantı kullanarak veritabanına bağlan
            with connections[db_name].cursor() as cursor:
                cursor.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
                tables = cursor.fetchall()
                return render(request, 'use_database.html', {
                    'success': True,
                    'tables': tables,
                    'db_name': db_name
                })
        except Exception as e:
            return render(request, 'use_database.html', {
                'success': False,
                'error': str(e)
            })
    else:
        return render(request, 'use_database.html') 














































































# class StartBrokerConnection(View):#-Mevcut olan veritabanına bağlanıp gelen verileri işleme
#     def __init__(self):
#         super().__init__()
#         self.client = None
#         self.user_column_names=[]

#     def post(self, request):#tablo adına göre mqtt bağlantısı oluşturma
#         table_name = request.POST.get('table_name')

#         if not table_name:
#             return JsonResponse({'error': 'Tablo adı sağlanmadı.'}, status=400)

#         broker_conns=BrokerConnection.objects.filter(topic=table_name)

#         if not broker_conns.exists():
#             return JsonResponse({'eror':'Broker bağlantısı bulunmadı'},status=404)
        

#         # Eğer birden fazla kayıt varsa, ilk kaydı kullanabilirsiniz
#         broker_conn = broker_conns.first()
#         broker_ip = broker_conn.broker_ip
#         port = broker_conn.port
#         username = broker_conn.username
#         password = broker_conn.password


#         #kullanıcıdan gelen kolon bilgileri
#         self.user_column_names=request.POST.getlist('user-column-name')
#         self.user_column_types=request.POST.getlist('user-column-type')



#         self.client = mqtt.Client()
#         self.client.username_pw_set(username, password)

#         def on_connect(client, userdata, flags, rc):
#             if rc == 0:#bağlantı başarılıysa
#                 print("Bağlantı başarıyla sağlandı.")
#                 client.subscribe(table_name)  
#             else:
#                 print(f"Bağlantı hatası, kod: {rc}")

#         def on_message(client, userdata, msg):#gelen messajları veritabanına kaydetme işlemi
#             print(f"Gelen mesaj: {msg.topic} - {msg.payload.decode()}")
#             try:
#                 json_data = json.loads(msg.payload.decode())
#                 print(f"Gelen JSON verisi: {json_data}")

#                 conn = psycopg2.connect(
#                     dbname='broker',
#                     user='postgres',
#                     password='123',
#                     host='localhost',
#                     port='5432'
#                 )
#                 cursor = conn.cursor()

#                 #Gelen veriden sütun adlarını ve değerlerini hazırlayın
#                 columns = []
#                 values = []

#                 for name in self.user_column_names:
#                     if name in json_data:
#                         value=json_data[name]
#                         if value is None or value=="":
#                             values.append(None)
#                         else:
#                             values.append(value)
#                         columns.append(name)

#                 #Sorgu Verştabanı kayıt alanı
#                 if columns:
#                     insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(['%s'] * len(values))});"
#                     try:
#                         cursor.execute(insert_query, values)
#                         conn.commit()
#                         print("Veri başarıyla kaydedildi.")
#                     except Exception :
#                         print("Veri kaydetme hatası: {Exception}") # Detaylı hata mesajı
#                 else:
#                     print("Veri kaydedilemedi")
#             except json.JSONDecodeError:
#                 print("JSON çözümleme hatası.")
#             except Exception as e:
#                 print(f"Veritabanı hatası: {e}")
#             finally:
#                 if cursor:
#                     cursor.close()
#                 if conn:
#                     conn.close()

#         self.client.on_connect = on_connect
#         self.client.on_message = on_message

#         try:
#             self.client.connect(broker_ip, port, 60)
#             Thread(target=self.client.loop_forever).start()  #mqtt dinleyicisini başlat - thread işlerin eş zamanlı yürümesine
#         except Exception as e:
#             print(f"MQTT bağlantı hatası: {e}")
#             return JsonResponse({'error': 'MQTT bağlantısı sağlanamadı.'}, status=500)

#         return JsonResponse({'message': f'Broker bağlantısı "{table_name}" için başlatıldı.'})


#     def stop_broker_connection(self):
#         if self.client:
#             self.client.disconnect()
#             print("Broker bağlantısı durduruldu.")
